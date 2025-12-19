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
    from .config_openai import *
elif llm_provider == "ollama":
    from .config_ollama import *
elif openai_api_key:
    from .config_openai import *
else:
    from .config_ollama import *
