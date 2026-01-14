"""
Complete Ollama Integration Example
Demonstrates how to use the Local LLM Skills System with Ollama
"""

import ollama
from pathlib import Path
import sys

# Import the skills system (assumes you saved it as local_skills.py)
# from local_skills import LocalLLMSkillsAgent, SkillManager

# For this example, we'll include a simplified version inline


class OllamaSkillsAgent:
    """
    Skills-enhanced agent that works with Ollama
    """
    
    def __init__(self, model: str = "llama3", skills_directory: str = "./skills"):
        self.model = model
        self.skill_manager = SkillManager(skills_directory)
        self.conversation_history = []
        
        # Verify Ollama is available
        try:
            ollama.list()
            print(f"✅ Connected to Ollama")
            print(f"📦 Using model: {model}")
        except Exception as e:
            print(f"❌ Error connecting to Ollama: {e}")
            print("Make sure Ollama is running: ollama serve")
            sys.exit(1)
    
    def build_system_prompt(self, relevant_skills):
        """Build enhanced system prompt with skills"""
        base_prompt = """You are a helpful AI assistant with access to specialized skills.

When responding to requests, carefully review any active skills below and follow their instructions precisely.
"""
        
        if relevant_skills:
            base_prompt += "\n## ACTIVE SKILLS\n\n"
            for skill in relevant_skills:
                base_prompt += f"### {skill.name}\n\n"
                base_prompt += skill.content + "\n\n"
                base_prompt += "---\n\n"
        
        return base_prompt
    
    def chat(self, user_message: str, temperature: float = 0.7, use_skills: bool = True):
        """
        Send a message and get a response with skill enhancement
        """
        relevant_skills = []
        
        # Discover and load relevant skills
        if use_skills:
            relevant_skills = self.skill_manager.select_relevant_skills(user_message, max_skills=2)
            
            if relevant_skills:
                skill_names = [s.name for s in relevant_skills]
                print(f"\n🔧 Activating skills: {', '.join(skill_names)}")
        
        # Build messages with system prompt
        system_prompt = self.build_system_prompt(relevant_skills)
        
        messages = [
            {'role': 'system', 'content': system_prompt},
            *self.conversation_history,
            {'role': 'user', 'content': user_message}
        ]
        
        # Call Ollama
        try:
            print(f"\n💭 Thinking...")
            
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    'temperature': temperature,
                }
            )
            
            assistant_message = response['message']['content']
            
            # Update conversation history
            self.conversation_history.append({'role': 'user', 'content': user_message})
            self.conversation_history.append({'role': 'assistant', 'content': assistant_message})
            
            return {
                'response': assistant_message,
                'skills_used': [s.name for s in relevant_skills],
                'model': self.model
            }
            
        except Exception as e:
            return {
                'response': f"Error: {e}",
                'skills_used': [],
                'model': self.model
            }
    
    def stream_chat(self, user_message: str, use_skills: bool = True):
        """
        Stream the response for real-time output
        """
        relevant_skills = []
        
        if use_skills:
            relevant_skills = self.skill_manager.select_relevant_skills(user_message, max_skills=2)
            
            if relevant_skills:
                skill_names = [s.name for s in relevant_skills]
                print(f"\n🔧 Activating skills: {', '.join(skill_names)}")
        
        system_prompt = self.build_system_prompt(relevant_skills)
        
        messages = [
            {'role': 'system', 'content': system_prompt},
            *self.conversation_history,
            {'role': 'user', 'content': user_message}
        ]
        
        print(f"\n💭 Assistant: ", end='', flush=True)
        
        full_response = ""
        
        try:
            stream = ollama.chat(
                model=self.model,
                messages=messages,
                stream=True
            )
            
            for chunk in stream:
                content = chunk['message']['content']
                print(content, end='', flush=True)
                full_response += content
            
            print()  # New line after streaming
            
            # Update history
            self.conversation_history.append({'role': 'user', 'content': user_message})
            self.conversation_history.append({'role': 'assistant', 'content': full_response})
            
            return {
                'response': full_response,
                'skills_used': [s.name for s in relevant_skills]
            }
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return {
                'response': f"Error: {e}",
                'skills_used': []
            }
    
    def reset(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("🔄 Conversation reset")
    
    def list_skills(self):
        """Show all available skills"""
        print(self.skill_manager.get_all_skills_summary())


# Simple SkillManager stub for this example
class SkillManager:
    def __init__(self, skills_directory):
        self.skills_directory = Path(skills_directory)
        self.skills = []
        print(f"📁 Skills directory: {self.skills_directory}")
    
    def select_relevant_skills(self, query, max_skills=2):
        return []  # Simplified - use full implementation from main file
    
    def get_all_skills_summary(self):
        return "Use the full implementation to load skills"


def interactive_mode():
    """
    Interactive CLI for chatting with Ollama + Skills
    """
    print("=" * 70)
    print("🤖 Ollama Skills Agent - Interactive Mode")
    print("=" * 70)
    print("\nCommands:")
    print("  /reset    - Clear conversation history")
    print("  /skills   - List available skills")
    print("  /model    - Change model")
    print("  /quit     - Exit")
    print("\n" + "=" * 70 + "\n")
    
    # Initialize agent
    agent = OllamaSkillsAgent(model="llama3", skills_directory="./skills")
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith('/'):
                if user_input == '/quit':
                    print("\n👋 Goodbye!")
                    break
                elif user_input == '/reset':
                    agent.reset()
                    continue
                elif user_input == '/skills':
                    agent.list_skills()
                    continue
                elif user_input.startswith('/model'):
                    parts = user_input.split()
                    if len(parts) > 1:
                        agent.model = parts[1]
                        print(f"✅ Switched to model: {agent.model}")
                    else:
                        print(f"Current model: {agent.model}")
                    continue
                else:
                    print("Unknown command")
                    continue
            
            # Stream the response
            result = agent.stream_chat(user_input)
            
            if result['skills_used']:
                print(f"\n✨ Skills used: {', '.join(result['skills_used'])}")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def example_usage():
    """
    Programmatic usage example
    """
    print("=" * 70)
    print("📝 Programmatic Usage Example")
    print("=" * 70)
    
    # Create agent
    agent = OllamaSkillsAgent(model="llama3")
    
    # Example queries
    queries = [
        "Create a Q4 2024 sales report for the Northeast region",
        "What's the capital of France?",
        "Write a Python function to calculate fibonacci numbers"
    ]
    
    for query in queries:
        print(f"\n{'=' * 70}")
        print(f"Query: {query}")
        print('=' * 70)
        
        result = agent.chat(query)
        print(f"\n{result['response']}")
        
        if result['skills_used']:
            print(f"\n✨ Skills used: {', '.join(result['skills_used'])}")
        
        print()


if __name__ == "__main__":
    # Run interactive mode by default
    # Uncomment example_usage() to see programmatic examples
    
    interactive_mode()
    # example_usage()