import os
from dotenv import load_dotenv

load_dotenv()

llm_provider = os.getenv("LLM_PROVIDER").lower()
openai_api_key = os.getenv("OPENAI_API_KEY")
ollama_api_key = os.getenv("OLLAMA_API_KEY")

# Logic to determine which config to load
# Priority:
# 1. LLM_PROVIDER env var (explicit choice)
# 2. Presence of OPENAI_API_KEY -> OpenAI
# 3. Default -> Ollama

if llm_provider == "openai":
    print(f"Loading OpenAI Configuration (Provider: {llm_provider})")
    from .config_openai import *
elif llm_provider == "ollama":
    print(f"Loading Ollama Configuration (Provider: {llm_provider})")
    from .config_ollama import *
elif openai_api_key:
    print("Loading OpenAI Configuration (Auto-detected API Key)")
    from .config_openai import *
else:
    print("Loading Ollama Configuration (Default)")
    from .config_ollama import *
