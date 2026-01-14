"""
Enhanced Ollama Agent with Automatic R Plot Execution and Display

Drop-in replacement for your existing agent that automatically:
1. Detects R code in responses
2. Executes the code
3. Saves and displays the plot

Usage:
    from enhanced_agent import EnhancedOllamaAgent
    
    agent = EnhancedOllamaAgent()
    agent.chat("Plot y = x² in R")
    # Plot automatically executes and opens!
"""

import ollama
import subprocess
import os
import re
import platform
from pathlib import Path

from log_setup import configure_logging
logger = configure_logging()

class EnhancedOllamaAgent:
    """
    Ollama agent with automatic R code execution and plot display
    """
    
    def __init__(self, 
                 model: str = "llama3", 
                 skills_directory: str = "./skills",
                 auto_execute_r: bool = True,
                 auto_display_plots: bool = True,
                 save_plots_to: str = "./plots"):
        logger.info("Setting up skills")
        # Import the base skills system
        try:
            from local_skills import SkillManager
            self.skill_manager = SkillManager(skills_directory)
        except ImportError:
            print("⚠️  Warning: Could not import SkillManager")
            print("   Skills will not be loaded. This is OK for basic usage.")
            self.skill_manager = None
        
        self.model = model
        self.conversation_history = []
        self.auto_execute_r = auto_execute_r
        logger.debug(f"Auto executing R code: {self.auto_execute_r}")
        self.auto_display_plots = auto_display_plots
        self.save_plots_to = Path(save_plots_to)
        
        # Create plots directory
        self.save_plots_to.mkdir(exist_ok=True)
        
        # Verify Ollama connection
        try:
            ollama.list()
            print(f"✅ Connected to Ollama (model: {model})")
        except Exception as e:
            print(f"❌ Error connecting to Ollama: {e}")
            print("   Make sure Ollama is running: ollama serve")
    
    def _extract_code_blocks(self, text: str, language: str = 'r') -> list:
        """Extract code blocks of a specific language from markdown"""
        pattern = rf'```{language}\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        return matches
    
    def _execute_r_code(self, r_code: str) -> dict:
        """Execute R code and return results"""
        logger.info("Executing R code")
        script_name = "temp_script.R"
        script_path = os.path.join(self.save_plots_to, script_name)
        
        try:
            self.save_plots_to.mkdir(parents=True, exist_ok=True)
            # Write R code to temp file
            with open(script_path, 'w') as f:
                f.write(r_code)
            
            # Execute with Rscript
            logger.debug(f"script_path: {str(script_path)}")
            result = subprocess.run(
                ['Rscript', str(script_name)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.save_plots_to)  # Run in plots directory
            )
            
            # Check for errors
            if result.returncode != 0:
                # because Rscript somtimes puts startup errors in stdout:
                error_message = result.stderr + result.stdout
                logger.error(f"Return code was not zero. Error: {error_message}")
                return {
                    'success': False,
                    'error': error_message,
                    'output': "None",
                    'plot_files': []
                }
            
            # Find generated plot files
            plot_extensions = ['.png', '.pdf', '.jpg', '.jpeg', '.svg']
            plot_files = []
            
            for file in self.save_plots_to.iterdir():
                if file.is_file() and file.suffix.lower() in plot_extensions:
                    # Check if file was created recently (within last 5 seconds)
                    if (file.stat().st_mtime > (os.path.getmtime(script_path) - 5)):
                        plot_files.append(file)
            
            return {
                'success': True,
                'output': result.stdout,
                'error': None,
                'plot_files': plot_files
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Process timed out")
            return {
                'success': False,
                'error': 'R script execution timed out (60s limit)',
                'output': '',
                'plot_files': []
            }
        except FileNotFoundError as fnfe:
            logger.error(fnfe)
            return {
                'success': False,
                'error': 'Rscript not found. Make sure R is installed and in PATH.',
                'output': '',
                'plot_files': []
            }
        except Exception as e:
            logger.error(e)
            return {
                'success': False,
                'error': str(e),
                'output': '',
                'plot_files': []
            }
        finally:
            # Clean up temp script
            logger.warning(f"NOT removing script: {script_path}")
#            if script_path.exists():
#                script_path.unlink()
    
    def _display_plot(self, plot_path: Path):
        """Open plot in system's default viewer"""
        if not plot_path.exists():
            print(f"❌ Plot file not found: {plot_path}")
            return False
        
        system = platform.system()
        
        try:
            if system == 'Darwin':  # macOS
                subprocess.run(['open', str(plot_path)], check=True)
            elif system == 'Windows':
                os.startfile(str(plot_path))
            else:  # Linux
                subprocess.run(['xdg-open', str(plot_path)], check=True)
            
            return True
        except Exception as e:
            print(f"⚠️  Could not auto-open plot: {e}")
            print(f"   You can manually open: {plot_path}")
            return False
    
    def _build_system_prompt(self, relevant_skills: list) -> str:
        """Build system prompt with active skills"""
        prompt = "You are a helpful AI assistant"
        
        if relevant_skills:
            prompt += " with access to specialized skills.\n\n"
            prompt += "## Active Skills\n\n"
            
            for skill in relevant_skills:
                prompt += f"### {skill.name}\n\n"
                prompt += skill.content + "\n\n---\n\n"
        else:
            prompt += ".\n\n"
        
        return prompt
    
    def chat(self, user_message: str, temperature: float = 0.7) -> dict:
        """
        Chat with automatic R code execution
        
        Returns:
            dict with 'response', 'skills_used', 'r_executed', 'plot_files'
        """
        # Select relevant skills
        relevant_skills = []
        if self.skill_manager:
            relevant_skills = self.skill_manager.select_relevant_skills(
                user_message, max_skills=2
            )
            
            if relevant_skills:
                skill_names = [s.name for s in relevant_skills]
                print(f"🔧 Using skills: {', '.join(skill_names)}")
        
        # Build messages
        system_prompt = self._build_system_prompt(relevant_skills)
        
        messages = [
            {'role': 'system', 'content': system_prompt},
            *self.conversation_history,
            {'role': 'user', 'content': user_message}
        ]
        
        # Call Ollama
        print("💭 Thinking...")
        
        try:
            logger.debug("Calling Ollama")
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={'temperature': temperature}
            )
            
            assistant_message = response['message']['content']
            
            # Update conversation history
            self.conversation_history.append({
                'role': 'user', 
                'content': user_message
            })
            self.conversation_history.append({
                'role': 'assistant', 
                'content': assistant_message
            })
            
            # Check for R code
            r_code_blocks = self._extract_code_blocks(assistant_message, 'r')
            
            result = {
                'response': assistant_message,
                'skills_used': [s.name for s in relevant_skills],
                'r_executed': False,
                'plot_files': []
            }
            logger.debug(f"r_code_blocks: {r_code_blocks}")
            # Execute R code if found
            if r_code_blocks and self.auto_execute_r:
                print("\n🔬 R code detected - executing...")
                
                for i, r_code in enumerate(r_code_blocks, 1):
                    exec_result = self._execute_r_code(r_code)
                    
                    if exec_result['success']:
                        print(f"✅ R code block {i} executed successfully")
                        
                        if exec_result['output']:
                            print(f"📊 Output:\n{exec_result['output']}")
                        
                        result['r_executed'] = True
                        result['plot_files'].extend(exec_result['plot_files'])
                        
                        # Display plots
                        if exec_result['plot_files'] and self.auto_display_plots:
                            for plot_file in exec_result['plot_files']:
                                print(f"💾 Plot saved: {plot_file}")
                                print(f"🖼️  Opening plot...")
                                self._display_plot(plot_file)
                    else:
                        print(f"❌ R code block {i} failed:")
                        print(f"   {exec_result['error']}")
                        result['r_error'] = exec_result['error']
            
            return result
            
        except Exception as e:
            return {
                'response': f"Error: {e}",
                'skills_used': [],
                'r_executed': False,
                'plot_files': []
            }
    
    def stream_chat(self, user_message: str, temperature: float = 0.7) -> dict:
        """Stream chat with R execution after completion"""
        # Select relevant skills
        relevant_skills = []
        if self.skill_manager:
            relevant_skills = self.skill_manager.select_relevant_skills(
                user_message, max_skills=2
            )
            
            if relevant_skills:
                skill_names = [s.name for s in relevant_skills]
                print(f"🔧 Using skills: {', '.join(skill_names)}")
        
        # Build messages
        system_prompt = self._build_system_prompt(relevant_skills)
        
        messages = [
            {'role': 'system', 'content': system_prompt},
            *self.conversation_history,
            {'role': 'user', 'content': user_message}
        ]
        
        print("💭 Assistant: ", end='', flush=True)
        
        full_response = ""
        
        try:
            stream = ollama.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options={'temperature': temperature}
            )
            
            for chunk in stream:
                content = chunk['message']['content']
                print(content, end='', flush=True)
                full_response += content
            
            print()  # Newline
            
            # Update history
            self.conversation_history.append({
                'role': 'user',
                'content': user_message
            })
            self.conversation_history.append({
                'role': 'assistant',
                'content': full_response
            })
            
            # Check for and execute R code
            result = {
                'response': full_response,
                'skills_used': [s.name for s in relevant_skills],
                'r_executed': False,
                'plot_files': []
            }
            
            r_code_blocks = self._extract_code_blocks(full_response, 'r')
            
            if r_code_blocks and self.auto_execute_r:
                print("\n🔬 R code detected - executing...")
                
                for r_code in r_code_blocks:
                    exec_result = self._execute_r_code(r_code)
                    
                    if exec_result['success']:
                        print("✅ Executed successfully")
                        result['r_executed'] = True
                        result['plot_files'].extend(exec_result['plot_files'])
                        
                        if exec_result['plot_files'] and self.auto_display_plots:
                            for plot_file in exec_result['plot_files']:
                                print(f"💾 Saved: {plot_file}")
                                self._display_plot(plot_file)
                    else:
                        print(f"❌ Failed: {exec_result['error']}")
            
            return result
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return {
                'response': full_response or f"Error: {e}",
                'skills_used': [],
                'r_executed': False,
                'plot_files': []
            }
    
    def reset(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("🔄 Conversation reset")
    
    def list_skills(self):
        """List available skills"""
        if self.skill_manager:
            print(self.skill_manager.get_all_skills_summary())
        else:
            print("No skill manager loaded")


def interactive_mode():
    """Interactive CLI with automatic plot display"""
    print("="*70)
    print("🤖 Enhanced Ollama Agent with Auto Plot Display")
    print("="*70)
    print("\nCommands:")
    print("  /reset    - Clear conversation")
    print("  /skills   - List skills")
    print("  /plots    - Show saved plots directory")
    print("  /toggle   - Toggle auto-execution on/off")
    print("  /quit     - Exit")
    print("\n" + "="*70 + "\n")
    
    agent = EnhancedOllamaAgent(
        model="llama3",
        skills_directory="./skills",
        auto_execute_r=True,
        auto_display_plots=True
    )
    
    print(f"💾 Plots will be saved to: {agent.save_plots_to.absolute()}")
    print(f"⚙️  Auto-execute R: {agent.auto_execute_r}")
    print(f"🖼️  Auto-display plots: {agent.auto_display_plots}\n")
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
            
            # Commands
            if user_input == '/quit':
                print("\n👋 Goodbye!")
                break
            elif user_input == '/reset':
                agent.reset()
                continue
            elif user_input == '/skills':
                agent.list_skills()
                continue
            elif user_input == '/plots':
                print(f"\n📁 Plots directory: {agent.save_plots_to.absolute()}")
                plots = list(agent.save_plots_to.glob('*'))
                if plots:
                    print(f"   Contains {len(plots)} file(s):")
                    for plot in plots[:10]:
                        print(f"   - {plot.name}")
                else:
                    print("   (empty)")
                continue
            elif user_input == '/toggle':
                agent.auto_execute_r = not agent.auto_execute_r
                print(f"⚙️  Auto-execute R: {agent.auto_execute_r}")
                continue
            
            # Regular chat
            result = agent.stream_chat(user_input)
            
            if result['r_executed'] and result['plot_files']:
                print(f"\n✨ Generated {len(result['plot_files'])} plot(s)")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    interactive_mode()
