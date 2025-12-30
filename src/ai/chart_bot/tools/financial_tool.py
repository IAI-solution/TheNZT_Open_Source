import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://fmp.iaisolution.com/api/v1"
API_KEY = os.getenv("BIG_AIR_LAB_FINANCE_API_KEY")

# --- Placeholder Config (Replace with your actual project modules) ---
# In a real project, you would likely load this from a config file or environment variable.
FMP_BASE_URL = "https://financialmodelingprep.com"
FMP_API_KEY = os.getenv("FM_API_KEY")

TIMEOUT = 30.0


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

# CORE API FUNCTIONS

async def _fetch_from_backend(endpoint: str, params: dict) -> dict:
    """Fetch data from backend API."""
    if not API_KEY:
        raise RuntimeError("BIG_AIR_LAB_FINANCE_API_KEY not configured")
    
    url = f"{BASE_URL}/{endpoint}"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(
            url,
            params=params,
            headers={"Finance-API-Key": API_KEY}
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Backend API Error {response.status_code}: {response.text}")

        return response.json()


async def _fetch_from_fmp(endpoint: str, params: dict) -> dict:
    """Fetch data directly from FMP API (fallback)."""
    if not FMP_API_KEY:
        raise RuntimeError("FM_API_KEY not configured for fallback")
    
    url = f"{FMP_BASE_URL}/{endpoint}"
    params["apikey"] = FMP_API_KEY
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params=params)
        
        if response.status_code != 200:
            raise RuntimeError(f"FMP API Error {response.status_code}: {response.text}")
        
        return response.json()


# --- Tool Definitions ---
@tool(args_schema=HistoricalPriceInput)
async def fetch_stock_price_history(ticker: str, from_date: str = None, to_date: str = None) -> dict:
    """
    Fetches the end-of-day historical price data for a given stock ticker.
    Use this for specific date range queries for STOCKS.
    Tries backend API first, falls back to FMP direct if backend fails.
    """
    print(f"fetch_stock_price_history({ticker}, from={from_date}, to={to_date})")
    
    backend_error = None
    fmp_error = None
    
    # Build params
    params = {"symbol": ticker}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date
    
    # Try backend API first
    try:
        print(f"Attempting backend API for {ticker}...")
        result = await _fetch_from_backend("market-data/historical", params)
        result["_source"] = "backend"
        return result
    except Exception as e:
        backend_error = str(e)
        print(f"Backend failed: {backend_error[:100]}...")
    
    # Fallback to FMP direct
    try:
        print(f"Falling back to FMP direct for {ticker}...")
        
        # FMP uses different param names
        fmp_params = {"symbol": ticker}
        if from_date:
            fmp_params["from"] = from_date
        if to_date:
            fmp_params["to"] = to_date
        
        result = await _fetch_from_fmp("stable/historical-price-eod/full", fmp_params)
        
        # Wrap result to match expected structure
        if isinstance(result, list):
            result = {"data": result, "_source": "fmp_fallback"}
        elif isinstance(result, dict):
            result["_source"] = "fmp_fallback"
        
        return result
    except Exception as e:
        fmp_error = str(e)
        print(f"FMP fallback also failed: {fmp_error[:100]}...")
    
    # Both failed
    error_msg = f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}"
    print(f"{error_msg}")
    return {"error": error_msg, "ticker": ticker}


@tool(args_schema=CryptoHistoricalPriceInput)
async def fetch_crypto_price_history(symbol: str, from_date: str = None, to_date: str = None) -> dict:
    """
    Fetches the end-of-day historical price data for a given cryptocurrency symbol.
    Tries backend API first, falls back to FMP direct if backend fails.
    """
    print(f"fetch_crypto_price_history({symbol}, from={from_date}, to={to_date})")
    
    backend_error = None
    fmp_error = None
    
    # Build params
    params = {"symbol": symbol, "data_type": "crypto"}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date
    
    # Try backend API first
    try:
        print(f"Attempting backend API for crypto {symbol}...")
        result = await _fetch_from_backend("market-data/historical", params)
        result["_source"] = "backend"
        return result
    except Exception as e:
        backend_error = str(e)
        print(f"Backend failed: {backend_error[:100]}...")
    
    # Fallback to FMP direct
    try:
        print(f"Falling back to FMP direct for crypto {symbol}...")
        
        # FMP uses different param names
        fmp_params = {"symbol": symbol}
        if from_date:
            fmp_params["from"] = from_date
        if to_date:
            fmp_params["to"] = to_date
        
        result = await _fetch_from_fmp("stable/historical-price-eod/full", fmp_params)
        
        # Wrap result to match expected structure
        if isinstance(result, list):
            result = {"data": result, "_source": "fmp_fallback"}
        elif isinstance(result, dict):
            result["_source"] = "fmp_fallback"
    
        return result
    except Exception as e:
        fmp_error = str(e)
        print(f"FMP fallback also failed: {fmp_error[:100]}...")
    
    # Both failed
    error_msg = f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}"
    print(f"{error_msg}")
    return {"error": error_msg, "symbol": symbol}

# get_historical = get_historical_price_full()
# get_crypto_historical = get_crypto_historical_price_full()