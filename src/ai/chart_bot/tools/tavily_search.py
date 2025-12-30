from tavily import TavilyClient
import os
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class SearchInput(BaseModel):
    """Input schema for the tavily_web_search tool."""
    query: str = Field(..., description="The search query to find information on the web.")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

@tool(args_schema=SearchInput)
async def search_financial_web_content(query: str) -> dict:
    """
    A web search tool that uses the Tavily API to find information, news, or answer general questions.
    Use this for any query that is not a direct request for stock or crypto price data.
    """
    print(f"TOOL: Performing Tavily web search for: {query}...")
    if not TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY environment variable is not set."}

    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        response = tavily_client.search(
            query=query,
            max_results=5,
            include_raw_content=False,
            search_depth="basic", # Using 'advanced' for more comprehensive results
            include_answer=True, # Ask Tavily to provide a direct answer if possible
            topic="finance" # Focus the search on financial topics
        )
        return response
    except Exception as e:
        return {"error": f"An error occurred during the Tavily search: {e}"}