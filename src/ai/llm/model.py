# from langchain_community.chat_models import ChatLiteLLM
# # from langchain_litellm import ChatLiteLLM
# from dotenv import dotenv_values
# from typing import List, Optional, Any
# import os


# # os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
# # os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
# # os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
# os.environ["LITELLM_LOG"] = "ERROR"

# env_vars = dotenv_values('.env')
# openai_api_key = env_vars.get('OPENAI_API_KEY')
# gemini_api_key = env_vars.get('GEMINI_API_KEY')
# groq_api_key = env_vars.get('GROQ_API_KEY')

# if openai_api_key and not os.getenv("OPENAI_API_KEY"):
#     print('getting api key from env')
#     os.environ["OPENAI_API_KEY"] = openai_api_key
# if gemini_api_key and not os.getenv("GEMINI_API_KEY"):
#     print('getting api key from env')
#     os.environ["GEMINI_API_KEY"] = gemini_api_key
# if groq_api_key and not os.getenv("GROQ_API_KEY"):
#     print('getting api key from env')
#     os.environ["GROQ_API_KEY"] = groq_api_key


# def get_llm(model_name: str, temperature: float = None, max_tokens: int = None):
#     model = ChatLiteLLM(model_name=model_name, temperature=temperature, max_tokens=max_tokens, max_retries=2)
#     # model = ChatLiteLLM(model=model_name, temperature=temperature, max_tokens=max_tokens, max_retries=2)
#     return model


# def get_llm_groq(model_name: str , temperature: float = None, top_p: float = None, top_k: int = None) -> ChatLiteLLM:
#     return ChatLiteLLM(model=model_name, temperature=temperature, top_p=top_p, top_k=top_k)


# def get_llm_alt(model_name: str, temperature: float = None, max_tokens: int = None):
#     model = ChatLiteLLM(model= model_name, temperature=temperature, max_tokens=max_tokens)
#     return model


from langchain_community.chat_models import ChatLiteLLM
# from langchain_litellm import ChatLiteLLM
from dotenv import dotenv_values
from typing import List, Optional, Any
import os


# os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
# os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
# os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
os.environ["LITELLM_LOG"] = "ERROR"

env_vars = dotenv_values('.env')
openai_api_key = env_vars.get('OPENAI_API_KEY')
gemini_api_key = env_vars.get('GEMINI_API_KEY')
groq_api_key = env_vars.get('GROQ_API_KEY')
ollama_api_key = env_vars.get('OLLAMA_API_KEY')
ollama_api_base = env_vars.get('OLLAMA_API_BASE')

if openai_api_key and not os.getenv("OPENAI_API_KEY"):
    print('getting api key from env')
    os.environ["OPENAI_API_KEY"] = openai_api_key
if gemini_api_key and not os.getenv("GEMINI_API_KEY"):
    print('getting api key from env')
    os.environ["GEMINI_API_KEY"] = gemini_api_key
if groq_api_key and not os.getenv("GROQ_API_KEY"):
    print('getting api key from env')
    os.environ["GROQ_API_KEY"] = groq_api_key
if ollama_api_key and not os.getenv("OLLAMA_API_KEY"):
    print('getting api key from env')
    os.environ["OLLAMA_API_KEY"] = ollama_api_key
if ollama_api_base and not os.getenv("OLLAMA_API_BASE"):
    print('getting api base from env')
    os.environ["OLLAMA_API_BASE"] = ollama_api_base


import litellm
# from src.ai.llm.usage_monitor import usage_monitor

# Register usage monitor callback
# litellm.callbacks = [usage_monitor]

def get_llm(model_name: str, temperature: float = None, max_tokens: int = None, agent_name: str = None):
    model_kwargs = {}
    # Check if using Ollama models via OpenAI provider
    if ("gpt-oss" in model_name or "kimi" in model_name or "qwen" in model_name or "deepseek" in model_name or "minimax" in model_name) and os.environ.get("OLLAMA_API_KEY"):
        model_kwargs["api_base"] = "https://ollama.com/v1"
        model_kwargs["api_key"] = os.environ["OLLAMA_API_KEY"]
    
    # Prepare metadata for usage monitoring
    if agent_name:
        model_kwargs["metadata"] = {"agent_name": agent_name}
        model_kwargs["agent_name"] = agent_name # Fallback: pass directly in model_kwargs
        
    # Pass model_kwargs explicitly so ChatLiteLLM forwards them to litellm
    # Filter out metadata from top-level kwargs to avoid "multiple values" TypeError if ChatLiteLLM accepts it as named arg
    top_level_kwargs = {k: v for k, v in model_kwargs.items() if k != 'metadata'}
    
    model = ChatLiteLLM(
        model=model_name, 
        temperature=temperature, 
        max_tokens=max_tokens, 
        max_retries=2, 
        model_kwargs=model_kwargs,
        **top_level_kwargs 
    )
    return model


def get_llm_groq(model_name: str , temperature: float = None, top_p: float = None, top_k: int = None) -> ChatLiteLLM:
    return ChatLiteLLM(model=model_name, temperature=temperature, top_p=top_p, top_k=top_k)


def get_llm_alt(model_name: str, temperature: float = None, max_tokens: int = None, agent_name: str = None):
    model_kwargs = {}
    # Check if using Ollama models via OpenAI provider
    if ("gpt-oss" in model_name or "kimi" in model_name or "qwen" in model_name or "deepseek" in model_name or "minimax" in model_name) and os.environ.get("OLLAMA_API_KEY"):
        model_kwargs["api_base"] = "https://ollama.com/v1"
        model_kwargs["api_key"] = os.environ["OLLAMA_API_KEY"]
        
    if agent_name:
        model_kwargs["metadata"] = {"agent_name": agent_name}
        model_kwargs["agent_name"] = agent_name # Fallback

    top_level_kwargs = {k: v for k, v in model_kwargs.items() if k != 'metadata'}
    
    model = ChatLiteLLM(
        model=model_name, 
        temperature=temperature, 
        max_tokens=max_tokens, 
        model_kwargs=model_kwargs,
        **top_level_kwargs
    )
    return model

