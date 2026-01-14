from enhanced_ollama_agent import EnhancedOllamaAgent
agent = EnhancedOllamaAgent(model="llama3:latest", auto_execute_r=True, auto_display_plots=True)
agent.chat("Plot y = x^2 in R")
