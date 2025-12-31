from src.ai.llm.model import get_llm, get_llm_alt
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Tuple, Dict, Any
import json
import asyncio
from src.ai.llm.model import get_llm
from src.ai.llm.config import GetRelatedQueriesConfig
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
    print("From chart_bot_related_query")
    print(f"input = {input}")
        
    try:
        # model = get_llm(model_name="gemini/gemini-2.5-pro", temperature=0.2)
        model = get_llm(model_name=grqc.MODEL, temperature=grqc.TEMPERATURE)
        response = await model.ainvoke(input=input, response_format=RelatedQueries)

    except Exception as e:
        print(f"Falling back to alternate model: {str(e)}")
        try:
            # model = get_llm_alt("gemini/gemini-2.0-flash-lite", 0.6)
            model = get_llm_alt(model_name=grqc.ALT_MODEL, temperature=grqc.ALT_TEMPERATURE)
            response = await model.invoke(input=input, response_format=RelatedQueries)
        except Exception as e:
            print(f"Error occurred in fallback model: {str(e)}")
            raise e

    if response.content:
        related_queries = json.loads(response.content)['related_queries']

        return related_queries
    return []


# chart_bot_related_query(name="Tesla", ticker="TSLA", exchange="NASDAQ")
if __name__ == "__main__":
    result = asyncio.run(chart_bot_related_query(name="Reliance Industries Ltd", ticker="RELIANCE", exchange="NSE"))
    # result = asyncio.run(chart_bot_related_query(name="Bitcoin", ticker="BTCUSD", exchange="CRYPTO"))
    print(result)