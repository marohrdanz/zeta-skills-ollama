"""
Local LLM Skills System
A Claude Skills-like framework for local LLMs (Ollama, etc.)

Features:
- Automatic skill discovery and loading
- Progressive disclosure (only loads relevant skills)
- SKILL.md format compatible with Claude Skills
- Works with any LLM API (Ollama, LiteLLM, etc.)
"""

import os
import json
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any
import re

from log_setup import configure_logging
logger = configure_logging()


class Skill:
    """Represents a single skill with its metadata and content"""
    
    def __init__(self, skill_path: Path):
        self.path = skill_path
        self.name = None
        self.description = None
        self.content = None
        self.reference_files = {}
        self._load_skill()
    
    def _load_skill(self):
        """Load and parse the SKILL.md file"""
        skill_file = self.path / "SKILL.md"
        
        if not skill_file.exists():
            raise FileNotFoundError(f"SKILL.md not found in {self.path}")
        
        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
        
        if frontmatter_match:
            frontmatter_str = frontmatter_match.group(1)
            self.content = frontmatter_match.group(2)
            
            # Parse YAML
            metadata = yaml.safe_load(frontmatter_str)
            self.name = metadata.get('name', self.path.name)
            self.description = metadata.get('description', '')
        else:
            # No frontmatter, use whole content
            self.content = content
            self.name = self.path.name
            self.description = ""
        
        # Load reference files
        for file_path in self.path.rglob('*'):
            if file_path.is_file() and file_path.name != 'SKILL.md':
                rel_path = file_path.relative_to(self.path)
                self.reference_files[str(rel_path)] = file_path
    
    def get_full_context(self) -> str:
        """Get the complete skill context including all reference files"""
        context = f"# Skill: {self.name}\n\n"
        context += f"Description: {self.description}\n\n"
        context += self.content
        
        if self.reference_files:
            context += "\n\n## Reference Files\n"
            for rel_path in self.reference_files:
                context += f"- {rel_path}\n"
        
        return context
    
    def get_summary(self) -> str:
        """Get just the skill name and description for discovery"""
        return f"**{self.name}**: {self.description}"
    
    def read_reference_file(self, filename: str) -> Optional[str]:
        """Read a specific reference file if it exists"""
        if filename in self.reference_files:
            file_path = self.reference_files[filename]
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                # Binary file
                return f"[Binary file: {filename}]"
        return None


class SkillManager:
    """Manages skill discovery, selection, and loading"""
    
    def __init__(self, skills_directory: str = "./skills"):
        self.skills_directory = Path(skills_directory)
        self.skills: List[Skill] = []
        self._discover_skills()
    
    def _discover_skills(self):
        """Discover all skills in the skills directory"""
        if not self.skills_directory.exists():
            print(f"Creating skills directory: {self.skills_directory}")
            self.skills_directory.mkdir(parents=True)
            return
        
        # Look for subdirectories containing SKILL.md
        for skill_dir in self.skills_directory.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                try:
                    skill = Skill(skill_dir)
                    self.skills.append(skill)
                    print(f"Loaded skill: {skill.name}")
                except Exception as e:
                    print(f"Error loading skill from {skill_dir}: {e}")
    
    def get_all_skills_summary(self) -> str:
        """Get a summary of all available skills"""
        if not self.skills:
            return "No skills available."
        
        summary = "Available Skills:\n\n"
        for i, skill in enumerate(self.skills, 1):
            summary += f"{i}. {skill.get_summary()}\n"
        return summary
    
    def select_relevant_skills(self, user_query: str, max_skills: int = 3) -> List[Skill]:
        """
        Select skills relevant to the user's query based on keyword matching.
        This is a simple implementation - you could use embeddings for better matching.
        """
        if not self.skills:
            return []
        
        # Score each skill based on keyword overlap
        scored_skills = []
        query_lower = user_query.lower()
        
        for skill in self.skills:
            score = 0
            skill_text = (skill.name + " " + skill.description).lower()
            
            # Simple keyword matching
            words = query_lower.split()
            for word in words:
                if len(word) > 3 and word in skill_text:
                    score += 1
            
            if score > 0:
                scored_skills.append((score, skill))
        
        # Sort by score and return top N
        scored_skills.sort(reverse=True, key=lambda x: x[0])
        return [skill for _, skill in scored_skills[:max_skills]]
    
    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """Get a specific skill by name"""
        for skill in self.skills:
            if skill.name.lower() == name.lower():
                return skill
        return None


class LocalLLMSkillsAgent:
    """
    Main agent that coordinates between the LLM and skills system.
    This is where you'd integrate with Ollama or other LLM APIs.
    """
    
    def __init__(self, skills_directory: str = "./skills", llm_client=None):
        self.skill_manager = SkillManager(skills_directory)
        self.llm_client = llm_client  # Your Ollama/LLM client
        self.conversation_history = []
    
    def build_system_prompt(self, relevant_skills: List[Skill]) -> str:
        """Build a system prompt that includes relevant skills"""
        system_prompt = """You are a helpful AI assistant with access to specialized skills.

When a user's request matches one of your available skills, you should reference and follow the instructions in that skill.

"""
        
        if relevant_skills:
            system_prompt += "## Active Skills\n\n"
            for skill in relevant_skills:
                system_prompt += skill.get_full_context() + "\n\n"
            system_prompt += "---\n\n"
        
        system_prompt += "Respond to the user's query using the skills above when relevant.\n"
        
        return system_prompt
    
    def chat(self, user_message: str, use_skills: bool = True) -> Dict[str, Any]:
        """
        Process a user message with optional skill enhancement.
        Returns a dict with the response and metadata about which skills were used.
        """
        relevant_skills = []
        
        if use_skills:
            # Discover relevant skills
            relevant_skills = self.skill_manager.select_relevant_skills(user_message)
            
            if relevant_skills:
                print(f"\n🔧 Using skills: {', '.join(s.name for s in relevant_skills)}\n")
        
        # Build the enhanced prompt
        system_prompt = self.build_system_prompt(relevant_skills)
        
        # Here's where you'd call your actual LLM
        # This is a placeholder showing the structure
        """
        Example Ollama integration:
        
        import ollama
        
        response = ollama.chat(
            model='llama2',
            messages=[
                {'role': 'system', 'content': system_prompt},
                *self.conversation_history,
                {'role': 'user', 'content': user_message}
            ]
        )
        
        assistant_message = response['message']['content']
        """
        
        # Placeholder response
        assistant_message = f"[This is where the LLM response would go]\n\nSystem prompt would include:\n{system_prompt[:500]}..."
        
        # Track conversation
        self.conversation_history.append({'role': 'user', 'content': user_message})
        self.conversation_history.append({'role': 'assistant', 'content': assistant_message})
        
        return {
            'response': assistant_message,
            'skills_used': [s.name for s in relevant_skills],
            'system_prompt': system_prompt
        }
    
    def list_skills(self):
        """List all available skills"""
        print(self.skill_manager.get_all_skills_summary())
    
    def reset_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []


# Example usage and demo
if __name__ == "__main__":
    # Initialize the agent
    agent = LocalLLMSkillsAgent(skills_directory="./skills")
    
    print("=" * 60)
    print("Local LLM Skills System Demo")
    print("=" * 60)
    
    # List available skills
    print("\n📚 Discovered Skills:")
    agent.list_skills()
    
    # Example interaction
    print("\n" + "=" * 60)
    print("Example Interaction:")
    print("=" * 60)
    
    user_query = "Create a sales report for Q4 2024"
    print(f"\nUser: {user_query}")
    
    result = agent.chat(user_query)
    print(f"\nAssistant: {result['response']}")
    
    if result['skills_used']:
        print(f"\n✅ Skills activated: {', '.join(result['skills_used'])}")
    
    print("\n" + "=" * 60)
    print("\n💡 Integration Instructions:")
    print("""
1. Create a 'skills' directory in your project
2. Add skills as subdirectories with SKILL.md files
3. Replace the placeholder LLM call in the chat() method with your Ollama client
4. Run the agent and it will automatically use relevant skills

Example Ollama integration:

    import ollama
    
    # In the chat() method:
    response = ollama.chat(
        model='llama3',
        messages=[
            {'role': 'system', 'content': system_prompt},
            *self.conversation_history,
            {'role': 'user', 'content': user_message}
        ]
    )
    
    assistant_message = response['message']['content']
    """)
