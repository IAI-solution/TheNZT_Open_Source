import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
# --- Placeholder Config (Replace with your actual project modules) ---
# In a real project, you would likely load this from a config file or environment variable.
fm_api_key = os.getenv("FM_API_KEY")


# --- Pydantic Schemas for Tools ---

class HistoricalPriceInput(BaseModel):
    """Input schema for the get_historical_price_full tool."""
    ticker: str = Field(..., description="The stock ticker symbol, e.g., 'AAPL'.")
    from_date: str = Field(None, description="The start date for historical data in YYYY-MM-DD format.")
    to_date: str = Field(None, description="The end date for historical data in YYYY-MM-DD format.")

class CryptoHistoricalPriceInput(BaseModel):
    """Input schema for the get_crypto_historical_price_full tool."""
    symbol: str = Field(..., description="The cryptocurrency symbol, e.g., 'BTCUSD'.")
    from_date: str = Field(None, description="The start date for historical data in YYYY-MM-DD format.")
    to_date: str = Field(None, description="The end date for historical data in YYYY-MM-DD format.")


# --- Tool Definitions ---

@tool(args_schema=HistoricalPriceInput)
async def fetch_stock_price_history(ticker: str, from_date: str = None, to_date: str = None) -> dict:
    """
    Fetches the end-of-day historical price data for a given stock ticker.
    Use this for specific date range queries for STOCKS.
    """
    print(f"TOOL: Fetching EOD historical stock data for {ticker}...")

    if not fm_api_key or fm_api_key == "your_fmp_api_key_here":
        return {"error": "FMP API key is not configured."}

    url = "https://financialmodelingprep.com/stable/historical-price-eod/full"
    print(f"url = {url}")
    params = {
        "symbol": ticker,
        "apikey": fm_api_key,
    }

    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        print(f"response.json() = {response.json()}")
        return response.json()


@tool(args_schema=CryptoHistoricalPriceInput)
async def fetch_crypto_price_history(symbol: str, from_date: str = None, to_date: str = None) -> dict:
    """
    Fetches the end-of-day historical price data for a given cryptocurrency symbol.
    """
    print(f"TOOL: Fetching EOD historical crypto data for {symbol}...")

    if not fm_api_key or fm_api_key == "your_fmp_api_key_here":
        return {"error": "FMP API key is not configured."}

    url = "https://financialmodelingprep.com/stable/historical-price-eod/full"
    params = {
        "symbol": symbol,
        "apikey": fm_api_key,
    }

    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    async with httpx.AsyncClient() as client:
        print(url)
        response = await client.get(url, params=params)
        return response.json()


# get_historical = get_historical_price_full()
# get_crypto_historical = get_crypto_historical_price_full()