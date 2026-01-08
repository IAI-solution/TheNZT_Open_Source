from src.ai.llm.model import get_llm, get_llm_alt
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Tuple, Dict, Any
import json
import asyncio
import re
from src.ai.llm.model import get_llm
from src.ai.llm.config import GetRelatedQueriesConfig
from src.ai.llm.config import llm_provider

load_dotenv()

grqc = GetRelatedQueriesConfig()

class RelatedQueries(BaseModel):
    related_queries: Optional[List[str]] = Field(description="List of four stock chart or crypto chart related questions that are strictly related to stock or crypto mentioned")


async def chart_bot_related_query(name: str, ticker: str, exchange: str, context_data: List[dict]) -> List[str]:
    """
    Args:
        name: The name of the company or cryptocurrency.
        ticker: The ticker symbol (e.g., 'AAPL') or crypto symbol (e.g., 'BTCUSD').
        exchange: The exchange it trades on (e.g., 'NASDAQ' or 'Crypto').
    """
    
    # input = "The following are the user queries from previous interactions from oldest to latest:\n"
    system_prompt = """
    Generate 4 questions regarding stock chart or crypto chart for the following information.
    """

    if exchange.upper() == "CRYPTO":
        base_context = f"""
        **CONTEXT**
        - Crypto currency name: {name}
        - Crypto symbol: {ticker}

        **Other numerical data you need to consider:**
        {context_data}
        """
    else:
        base_context = f"""
        **CONTEXT FOR THIS QUERY**
        - Company Name: {name}
        - Ticker: {ticker}
        - Exchange: {exchange}

        **Other numerical data you need to consider:**
        {context_data}
        """

    input = system_prompt + base_context

    if llm_provider == "ollama":
        input += '''
        ### Output format:
        Return the related queries in a JSON object as specified by the schema below.
        Do not include any text outside the JSON object.
        '''
        schema_instruction = f"\n\nYou must return the output as a valid JSON object matching this schema:\n{json.dumps(RelatedQueries.model_json_schema(), indent=2)}\n\nDo not include any text outside the JSON object."
        input += schema_instruction
    
    print("From chart_bot_related_query")
    print(f"input = {input}")
        
    try:
        model = get_llm(model_name=grqc.MODEL, temperature=grqc.TEMPERATURE)
        
        if llm_provider == "ollama":
             response = await model.ainvoke(input=input)
        else:
             response = await model.ainvoke(input=input, response_format=RelatedQueries)

    except Exception as e:
        print(f"Falling back to alternate model: {str(e)}")
        try:
            model = get_llm_alt(model_name=grqc.ALT_MODEL, temperature=grqc.ALT_TEMPERATURE)
            if llm_provider == "ollama":
                response = await model.invoke(input=input)
            else:
                response = await model.invoke(input=input, response_format=RelatedQueries)
        except Exception as e:
            print(f"Error occurred in fallback model: {str(e)}")
            raise e

    if response.content:
        if llm_provider == "ollama":
            # Manual JSON extraction for Ollama
            try:
                response_content = response.content
                # Remove thinking section if present (DeepSeek style)
                response_without_thinking = re.sub(r'<think>.*?</think>', '', response_content, flags=re.DOTALL)
                
                # Extract JSON content from markdown blocks if present
                json_match = re.search(r'```json\s*(.*?)\s*```', response_without_thinking, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1).strip()
                else:
                    # Try to find the first { and last }
                    start = response_without_thinking.find('{')
                    end = response_without_thinking.rfind('}')
                    if start != -1 and end != -1:
                        json_content = response_without_thinking[start:end+1]
                    else:
                        json_content = response_without_thinking

                related_queries = json.loads(json_content)['related_queries']
                return related_queries
            except (json.JSONDecodeError, KeyError, Exception) as e:
                print(f"JSON parsing error for Ollama: {str(e)}")
                print("Raw content:", response.content)
                return []
        else:
            # Standard extraction for OpenAI/Azure
            try:
                related_queries = json.loads(response.content)['related_queries']
                return related_queries
            except Exception as e:
                print(f"Error parsing response content: {e}")
                return []
    return []


# chart_bot_related_query(name="Tesla", ticker="TSLA", exchange="NASDAQ")
if __name__ == "__main__":
    result = asyncio.run(chart_bot_related_query(name="Reliance Industries Ltd", ticker="RELIANCE", exchange="NSE"))
    # result = asyncio.run(chart_bot_related_query(name="Bitcoin", ticker="BTCUSD", exchange="CRYPTO"))
    print(result)