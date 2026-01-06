import os
import aiohttp          
import asyncio          
from typing import Dict, Any, Optional, List, Type          
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field      
from langchain_core.tools import BaseTool  

from dotenv import load_dotenv
load_dotenv()

BASE_URL = "https://fmp.iaisolution.com/api/v1"
API_KEY = os.getenv("BIG_AIR_LAB_FINANCE_API_KEY")

# FMP Direct API 
FMP_BASE_URL = "https://financialmodelingprep.com"
FMP_API_KEY = os.getenv("FM_API_KEY")

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)


def _to_str(value) -> Optional[str]:
    """Convert numeric value to string for frontend compatibility. Returns None if value is None."""
    if value is None:
        return None
    return str(value)


def _format_price(value) -> Optional[str]:
    """Format price value as string with 2 decimal places."""
    if value is None:
        return None
    try:
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return str(value)


def _format_volume(value) -> Optional[str]:
    """Format volume with comma separators."""
    if value is None:
        return None
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _format_date(date_str: str) -> str:
    """Convert date from 'YYYY-MM-DD' to 'Mon DD, YYYY' format."""
    if not date_str:
        return date_str
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return date_str


class TickerSchema(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g., 'AAPL', 'TSLA', 'RELIANCE.NS')")
    exchange_symbol: str = Field(..., description="Exchange short name (e.g., 'NASDAQ', 'NYSE', 'NSE', 'BSE', 'DFM')")


class StockDataSchema(BaseModel):
    ticker_data: List[TickerSchema] = Field(..., description="List of ticker objects with ticker and exchange_symbol")
    explanation: Optional[str] = Field(None, description="Brief explanation of why this data is needed")
    period: str = Field("1M", description="Time period for historical data: 1M, 3M, 6M, YTD, 1Y, 5Y, MAX")
    strictly: bool = Field(False, description="If True, only return data for the exact period specified")


class QueryRequest(BaseModel):
    query: str = Field(..., description="Search query - either a ticker symbol or company name")
    type: str = Field("ticker_symbol", description="Type of query: 'ticker_symbol' or 'company_name'")
    exchange_short_name: Optional[str] = Field(None, description="Exchange short name for filtering results")


class SearchCompanyInfoSchema(BaseModel):
    query_list: List[QueryRequest] = Field(..., description="List of search queries")
    explanation: Optional[str] = Field(None, description="Brief explanation of why this search is needed")
    

async def _get_backend(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make an async HTTP GET request to the backend API.
    
    Parameters:
    -----------
    endpoint : str
        The API endpoint path (e.g., "financial-statements/income-statement")
        This gets appended to BASE_URL to form the full URL
        
    params : Dict[str, Any]
        Query parameters to send with the request (e.g., {"symbol": "AAPL"})
        These become URL query parameters like ?symbol=AAPL&period=annual
    
    Returns:
    --------
    Dict[str, Any]
        The parsed JSON response from the API
    """
    # Construct the full URL by combining base URL with endpoint
    # Example: "https://fmp.iaisolution.com/api/v1" + "/" + "financial-statements/income-statement"
    url = f"{BASE_URL}/{endpoint}"
    
    async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as session:
        
        # Make the GET request with authentication header
        async with session.get(
            url,                                   
            params=params,                          
            headers={"Finance-API-Key": API_KEY}    # Authentication header
        ) as response:
            
            # Check if the request was successful (HTTP 200)
            if response.status != 200:
                # If not successful, read the error message and raise an exception
                error_text = await response.text()
                print(f"🔴 BACKEND FAILED: Status {response.status} | {endpoint}")
                raise RuntimeError(
                    f"Finance API Error {response.status} | {endpoint} | {error_text}"
                )
            
            # Try to parse the JSON response
            try:
                return await response.json()
            except Exception as e:
                # If JSON parsing fails, raise a descriptive error
                raise RuntimeError(f"Failed to parse JSON response: {e}")
            

async def _get_fmp(endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make async HTTP GET request directly to FMP API (fallback)."""
    if not FMP_API_KEY:
        print("🔴 FMP FALLBACK FAILED: FMP_API_KEY not configured")
        raise RuntimeError("FMP_API_KEY not configured for fallback")
    
    url = f"{FMP_BASE_URL}/{endpoint}"
    params = params or {}
    params["apikey"] = FMP_API_KEY
    
    print(f"🟡 FMP FALLBACK: Trying {endpoint}")
    
    async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"🔴 FMP FALLBACK FAILED: Status {response.status} | {endpoint}")
                raise RuntimeError(f"FMP API Error {response.status} | {endpoint} | {error_text}")
            print(f"🟢 FMP FALLBACK SUCCESS: {endpoint}")
            return await response.json()


# =============================================================================
# FINANCIAL STATEMENTS ENDPOINTS
# =============================================================================
# These functions fetch the three main financial statements:
# 1. Income Statement - Revenue, expenses, and profit/loss
# 2. Balance Sheet - Assets, liabilities, and equity
# 3. Cash Flow Statement - Cash movements in/out of the company

async def get_income_statement(symbol: str, period: str = "annual", limit: int = 5) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    # Try backend API first
    try:
        return await _get_backend(
            "financial-statements/income-statement",
            {"symbol": symbol, "period": period, "limit": limit}
        )
    except Exception as e:
        backend_error = str(e)
    
    # Fallback to FMP direct
    try:
        data = await _get_fmp(f"api/stable/income-statement?symbol={symbol}", {"period": period, "limit": limit})
        return {"data": data, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


async def get_balance_sheet(symbol: str, period: str = "annual", limit: int = 5) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend(
            "financial-statements/balance-sheet",
            {"symbol": symbol, "period": period, "limit": limit}
        )
    except Exception as e:
        backend_error = str(e)
    
    try:
        data = await _get_fmp(f"api/stable/balance-sheet-statement?symbol={symbol}", {"period": period, "limit": limit})
        return {"data": data, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


async def get_cash_flow(symbol: str, period: str = "annual", limit: int = 5) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend(
            "financial-statements/cash-flow",
            {"symbol": symbol, "period": period, "limit": limit}
        )
    except Exception as e:
        backend_error = str(e)
    
    try:
        data = await _get_fmp(f"api/stable/cash-flow-statement?symbol={symbol}", {"period": period, "limit": limit})
        return {"data": data, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


# =============================================================================
# MARKET DATA ENDPOINTS
# =============================================================================
# These functions fetch market-related data:
# 1. Key Metrics - Important financial ratios (P/E, ROE, etc.)
# 2. Financial Ratios - Detailed profitability/liquidity ratios
# 3. Historical Prices - Daily stock price data

async def get_key_metrics(symbol: str, period: str = "annual", limit: int = 5) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend(
            "market-data/key-metrics",
            {"symbol": symbol, "period": period, "limit": limit}
        )
    except Exception as e:
        backend_error = str(e)
    
    try:
        data = await _get_fmp(f"api/stable/key-metrics?symbol={symbol}", {"period": period, "limit": limit})
        return {"data": data, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


async def get_financial_ratios(symbol: str, period: str = "annual", limit: int = 5) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend(
            "market-data/ratios",
            {"symbol": symbol, "period": period, "limit": limit}
        )
    except Exception as e:
        backend_error = str(e)
    
    try:
        data = await _get_fmp(f"api/stable/ratios?symbol={symbol}", {"period": period, "limit": limit})
        return {"data": data, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


async def get_historical_prices(symbol: str, from_date: str, to_date: str, data_type: str = "stock") -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend(
            "market-data/historical",
            {"symbol": symbol, "from_date": from_date, "to_date": to_date, "data_type": data_type}
        )
    except Exception as e:
        backend_error = str(e)
    
    try:
        # FMP historical endpoint
        data = await _get_fmp(
            "stable/historical-price-eod/full",
            {"symbol": symbol, "from": from_date, "to": to_date}
        )
        # Format to match expected structure
        if isinstance(data, list):
            return {"data": data, "source": "fmp_fallback"}
        elif isinstance(data, dict) and "historical" in data:
            return {"data": data["historical"], "source": "fmp_fallback"}
        return {"data": data, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


# =============================================================================
# SEARCH ENDPOINTS
# =============================================================================


async def search_stocks(query: str, limit: int = 50) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend("search/stocks", {"query": query, "limit": limit})
    except Exception as e:
        backend_error = str(e)
    
    try:
        data = await _get_fmp("stable/search-name", {"query": query, "limit": limit})
        return {"results": data if isinstance(data, list) else [], "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


async def search_financial_statement_symbols(query: str, limit: int = 50) -> Dict[str, Any]:
    return await _get_backend("search/financial-statements", {"query": query, "limit": limit})


async def search_cryptocurrencies(query: str, limit: int = 50) -> Dict[str, Any]:
    return await _get_backend("search/crypto", {"query": query, "limit": limit})


async def search_commodities(query: str, limit: int = 50) -> Dict[str, Any]:
    return await _get_backend("search/commodities", {"query": query, "limit": limit})


async def search_indexes(query: str, limit: int = 50) -> Dict[str, Any]:
    return await _get_backend("search/indexes", {"query": query, "limit": limit})


# =============================================================================
# REAL-TIME DATA ENDPOINTS
# =============================================================================

async def get_realtime_quote(symbol: str) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend("realtime/quote", {"symbol": symbol})
    except Exception as e:
        backend_error = str(e)
    
    try:
        # FMP quote endpoint returns a list
        data = await _get_fmp(f"stable/quote?symbol={symbol}")
        if isinstance(data, list) and len(data) > 0:
            quote = data[0]
            # Format to match backend structure
            return {
                "data": {
                    "symbol": symbol,
                    "data": {
                        "symbol": quote.get("symbol", symbol),
                        "name": quote.get("name", symbol),
                        "price": quote.get("price"),
                        "change": quote.get("change"),
                        "changePercentage": quote.get("changesPercentage"),
                        "volume": quote.get("volume"),
                        "dayHigh": quote.get("dayHigh"),
                        "dayLow": quote.get("dayLow"),
                        "yearHigh": quote.get("yearHigh"),
                        "yearLow": quote.get("yearLow"),
                        "marketCap": quote.get("marketCap"),
                        "open": quote.get("open"),
                        "previousClose": quote.get("previousClose"),
                        "exchange": quote.get("exchange"),
                        "timestamp": quote.get("timestamp"),
                    }
                },
                "source": "fmp_fallback"
            }
        return {"data": {"symbol": symbol, "data": data}, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


async def get_company_profile(symbol: str) -> Dict[str, Any]:
    backend_error = None
    fmp_error = None
    
    try:
        return await _get_backend("realtime/profile", {"symbol": symbol})
    except Exception as e:
        backend_error = str(e)
    
    try:
        # FMP profile endpoint returns a list
        data = await _get_fmp(f"api/stable/profile?symbol={symbol}")
        if isinstance(data, list) and len(data) > 0:
            profile = data[0]
            return {
                "data": {
                    "symbol": symbol,
                    "data": profile
                },
                "source": "fmp_fallback"
            }
        return {"data": {"symbol": symbol, "data": data}, "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


async def search_companies_realtime(query: str, limit: int = 10, exchange: str = None) -> Dict[str, Any]:
    """
    Search for companies by name or ticker symbol.
    """
    backend_error = None
    fmp_error = None
    
    try:
        params = {"query": query, "limit": limit}
        if exchange:
            params["exchange"] = exchange
        return await _get_backend("realtime/search", params)
    except Exception as e:
        backend_error = str(e)
    
    try:
        data = await _get_fmp("stable/search-name", {"query": query, "limit": limit})
        return {"results": data if isinstance(data, list) else [], "source": "fmp_fallback"}
    except Exception as e:
        fmp_error = str(e)
    
    raise RuntimeError(f"Both APIs failed. Backend: {backend_error} | FMP: {fmp_error}")


# TOOLS

class FinancialStatementsTool(BaseTool):
    name: str = "get_financial_statements"
    description: str = """
    Fetch financial statements (income statement, balance sheet, or cash flow) 
    for a company. Provide the stock symbol and optionally specify which statement 
    type (income, balance, cash, or all), period (annual or quarter), and limit.
    """

    def _run(
        self,
        symbol: str,
        statement: str = "income",
        period: str = "annual",
        limit: int = 5
    ) -> Dict[str, Any]:
        return asyncio.run(self._arun(symbol, statement, period, limit))

    async def _arun(
        self,
        symbol: str,
        statement: str = "income",
        period: str = "annual",
        limit: int = 5
    ) -> Dict[str, Any]:
        try:
            if statement == "income":
                data = await get_income_statement(symbol, period, limit)
            elif statement == "balance":
                data = await get_balance_sheet(symbol, period, limit)
            elif statement == "cash":
                data = await get_cash_flow(symbol, period, limit)
            elif statement == "all":
                income, balance, cash = await asyncio.gather(
                    get_income_statement(symbol, period, limit),
                    get_balance_sheet(symbol, period, limit),
                    get_cash_flow(symbol, period, limit)
                )
                data = {"income": income, "balance": balance, "cash": cash}
            else:
                return {"symbol": symbol, "error": f"Unknown statement type: {statement}. Valid options: income, balance, cash, all"}

            return {"symbol": symbol, "statement": statement, "period": period, "data": data, "source": BASE_URL}
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}


class MarketDataTool(BaseTool):
    name: str = "market_data_tool"
    description: str = """
    Fetch market data including key metrics, financial ratios, and historical prices.
    For historical prices, provide from_date and to_date in YYYY-MM-DD format.
    """

    def _run(
        self,
        symbol: str,
        data_type: str = "key_metrics",
        period: str = "annual",
        limit: int = 5,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        return asyncio.run(self._arun(symbol, data_type, period, limit, from_date, to_date))

    async def _arun(
        self,
        symbol: str,
        data_type: str = "key_metrics",
        period: str = "annual",
        limit: int = 5,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            if data_type in ("key_metrics", "key-metrics"):
                data = await get_key_metrics(symbol, period, limit)
            elif data_type in ("ratios", "financial_ratios"):
                data = await get_financial_ratios(symbol, period, limit)
            elif data_type in ("historical", "historical_prices"):
                if not from_date or not to_date:
                    return {"symbol": symbol, "error": "from_date and to_date are required for historical data. Format: YYYY-MM-DD"}
                data = await get_historical_prices(symbol, from_date, to_date)
            else:
                return {"symbol": symbol, "error": f"Unknown data_type: {data_type}. Valid options: key_metrics, ratios, historical"}

            return {"symbol": symbol, "data_type": data_type, "period": period, "data": data, "source": BASE_URL}
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}


class SearchCompanyInfoTool(BaseTool):
    """
    Search tool matching the old interface for compatibility.
    """
    name: str = "search_company_info"
    description: str = """
    Use this function to search for the ticker symbol or company name of financial instruments such as stocks or Bitcoin (if stored). 
    You can pass multiple queries as a list. Each query must be either a ticker symbol (in uppercase, e.g., 'AAPL') or a company name (e.g., 'Apple', 'Drake & Scull').

    Suffix rules for ticker symbols based on exchange:
    - USA exchanges (e.g., NASDAQ, NYSE): use plain symbol (e.g., TSLA, AAPL).
    - DFM: append **.AE** (e.g., DSI → DSI.AE).
    - NSE: append **.NS** (e.g., TATAMOTORS → TATAMOTORS.NS).
    - BSE: append **.BO** (e.g., RELIANCE → RELIANCE.BO).

    The `query_list` input should be a list in this format:
    query_list: [
        {
            "query": "AAPL",
            "type": "ticker_symbol",
            "exchange_short_name": "NASDAQ"
        },
        {
            "query": "Drake & Scull",
            "type": "company_name",
            "exchange_short_name": "DFM"
        }
    ]
"""
    args_schema: Type[BaseModel] = SearchCompanyInfoSchema

    def _run(self, query_list: List[QueryRequest], explanation: str = None) -> Dict[str, Any]:
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(query_list, explanation)
                )
                return future.result()
        except RuntimeError:
            return asyncio.run(self._arun(query_list, explanation))
        # return asyncio.run(self._arun(query_list, explanation))

    async def _arun(self, query_list: List[QueryRequest], explanation: str = None) -> Dict[str, Any]:
        results = []
        
        for query_obj in query_list:
            try:
                search_result = await search_stocks(query_obj.query, limit=50)
                
                results.append({
                    "query": query_obj.query,
                    "type": query_obj.type,
                    "exchange_short_name": query_obj.exchange_short_name,
                    "fmp_data": search_result.get("results", []),
                    "source": [
                        "https://site.financialmodelingprep.com/",
                        f"https://finance.yahoo.com/lookup/?s={query_obj.query}"
                    ]
                })
            except Exception as e:
                results.append({
                    "query": query_obj.query,
                    "type": query_obj.type,
                    "exchange_short_name": query_obj.exchange_short_name,
                    "error": f"Error processing {query_obj.query}: {str(e)}",
                    "fmp_data": None,
                    "source": []
                })
        
        return {"results": results}


class GetStockData(BaseTool):
    """
    Stock data tool matching the old interface for compatibility.
    Returns realtime and historical data in the format expected by the frontend.
    """
    name: str = "get_stock_data"
    description: str = """Use this tool to get real-time stock quote data and historical stock prices of companies. The realtime stock data includes price, changes, market cap, PE ratio, and more.
    This tool generates a stock price chart which is only visible to the user.
"""
    args_schema: Type[BaseModel] = StockDataSchema

    def _run(
        self,
        ticker_data: List[TickerSchema],
        explanation: str = None,
        period: str = "1M",
        strictly: bool = False
    ) -> List[Dict[str, Any]]:
        return asyncio.run(self._arun(ticker_data, explanation, period, strictly))

    async def _arun(
        self,
        ticker_data: List[TickerSchema],
        explanation: str = None,
        period: str = "1M",
        strictly: bool = False
    ) -> List[Dict[str, Any]]:
        
        period_days = {
            "1M": 31, "1m": 31, "1mo": 31,
            "3M": 93, "3m": 93, "3mo": 93,
            "6M": 186, "6m": 186, "6mo": 186,
            "YTD": 365,
            "1Y": 365, "1y": 365,
            "5Y": 1825, "5y": 1825,
            "MAX": 3650,
        }
        
        periods_to_try = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]
        
        async def process_single_ticker(ticker_info: TickerSchema) -> Dict[str, Any]:
            ticker = ticker_info.ticker
            exchange_symbol = ticker_info.exchange_symbol
            result = {"realtime": None, "historical": None}
            
            today = datetime.now(timezone.utc).date()
            
            if strictly:
                days = period_days.get(period, 31)
                from_date = (today - timedelta(days=days)).isoformat()
                to_date = today.isoformat()
                periods_used = [period]
            else:
                days = period_days.get(period, 31)
                from_date = (today - timedelta(days=days)).isoformat()
                to_date = today.isoformat()
                periods_used = periods_to_try
            
            # Fetch realtime quote and historical data concurrently
            try:
                realtime_task = get_realtime_quote(ticker)
                profile_task = get_company_profile(ticker)
                historical_task = get_historical_prices(
                    symbol=ticker,
                    from_date=from_date,
                    to_date=to_date
                )
                
                realtime_response, profile_response, hist_response = await asyncio.gather(
                    realtime_task, profile_task, historical_task, return_exceptions=True
                )
                
                # Extract currency from profile response
                currency_value = None
                if isinstance(profile_response, dict) and not isinstance(profile_response, Exception):
                    profile_data = profile_response.get("data", {})
                    if isinstance(profile_data, dict) and 'data' in profile_data:
                        profile_data = profile_data['data']
                    
                    if isinstance(profile_data, dict):
                        currency_value = profile_data.get("currency")
                
                # Process realtime data
                if isinstance(realtime_response, Exception):
                    result["realtime"] = {"error": str(realtime_response), "symbol": ticker}
                elif isinstance(realtime_response, dict):
                    # Extract data from response
                    # rt_data = realtime_response.get("data", realtime_response)
                    # if isinstance(rt_data, dict):
                    rt_data = realtime_response.get("data", {})
                    if isinstance(rt_data, dict) and 'data' in rt_data:
                        rt_data = rt_data['data']
                        # Keep numeric values as-is for realtime data (frontend expects numbers)
                        result["realtime"] = {
                            "symbol": rt_data.get("symbol", ticker),
                            "name": rt_data.get("name", ticker),
                            "price": rt_data.get("price"),
                            "open": rt_data.get("open"),
                            "dayHigh": rt_data.get("dayHigh"),
                            "dayLow": rt_data.get("dayLow"),
                            "volume": rt_data.get("volume"),
                            "previousClose": rt_data.get("previousClose"),
                            "change": rt_data.get("change"),
                            "changesPercentage": rt_data.get("changePercentage"),
                            "marketCap": rt_data.get("marketCap"),
                            "yearHigh": rt_data.get("yearHigh"),
                            "yearLow": rt_data.get("yearLow"),
                            "exchange": rt_data.get("exchange", exchange_symbol),
                            "currency": rt_data.get("currency") or currency_value,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    else:
                        result["realtime"] = {"error": "Invalid realtime data format", "symbol": ticker}
                else:
                    result["realtime"] = {"error": "No realtime data", "symbol": ticker}
                
                # Process historical data
                if isinstance(hist_response, Exception):
                    result["historical"] = {"error": str(hist_response)}
                else:
                    historical_data = []
                    if isinstance(hist_response, dict):
                        if 'data' in hist_response:
                            inner_data = hist_response['data']
                            if isinstance(inner_data, dict) and 'data' in inner_data:
                                historical_data = inner_data.get('data', [])
                            elif isinstance(inner_data, list):
                                historical_data = inner_data
                        elif 'historical' in hist_response:
                            historical_data = hist_response.get('historical', [])
                    elif isinstance(hist_response, list):
                        historical_data = hist_response
                    
                    if historical_data:
                        is_active = False
                        last_entry = historical_data[0] if historical_data else None
                        if last_entry and last_entry.get('date'):
                            try:
                                last_date = datetime.strptime(last_entry['date'], "%Y-%m-%d").date()
                                days_diff = (today - last_date).days
                                is_active = days_diff <= 5
                            except:
                                is_active = False
                        
                        # Convert historical data to expected format
                        converted_historical = []
                        for entry in historical_data:
                            converted_entry = {
                                "date": _format_date(entry.get("date")),
                                "open": _format_price(entry.get("open")),
                                "high": _format_price(entry.get("high")),
                                "low": _format_price(entry.get("low")),
                                "close": _format_price(entry.get("close")),
                                "volume": _format_volume(entry.get("volume")),
                            }
                            converted_historical.append(converted_entry)
                            
                        converted_historical.reverse()
                        
                        result["historical"] = {
                            "source": "https://financialmodelingprep.com/",
                            "period": periods_used,
                            "data": converted_historical,
                            "is_active": is_active
                        }
                    else:
                        result["historical"] = {"error": "No historical data found"}
                    
            except Exception as e:
                result["historical"] = {"error": f"Failed to fetch data: {str(e)}"}
                result["realtime"] = {"error": f"Failed to fetch data: {str(e)}", "symbol": ticker}
            
            if result.get("historical") and "error" not in result["historical"] and result.get("realtime") and "error" not in result["realtime"]:
                result["message"] = "A graph has been generated and shown to the user so do not include this data in the response."
            else:
                result["message"] = "Generate a graph based on this data which is visible to the user."
            
            return result
        
        tasks = [process_single_ticker(t) for t in ticker_data]
        results = await asyncio.gather(*tasks)
        
        return list(results)


# Pre-created tool instances
get_financial_statements = FinancialStatementsTool()
search_company_info = SearchCompanyInfoTool()
get_stock_data = GetStockData()


tool_list = [
    get_financial_statements,
    search_company_info,
    get_stock_data,
]


async def main():
    print("=" * 60)
    print("Financial Data API Client - Test Suite")
    print("=" * 60)
    
    print("\n📌 Test 1: Search for 'Apple'")
    try:
        search_result = await search_stocks("Apple", limit=3)
        print(f"   Found {len(search_result.get('results', []))} results")
        if search_result.get('results'):
            first = search_result['results'][0]
            print(f"   First result: {first.get('symbol')} - {first.get('companyName')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n📌 Test 2: Get AAPL Realtime Quote")
    try:
        quote = await get_realtime_quote("AAPL")
        print(f"   Response received: {type(quote)}")
        print(f"   Raw response: {quote}")  # Debug: print full response
        if isinstance(quote, dict):
            data = quote.get('data', quote)
            print(f"   ✓ Price: {data.get('price')}")
            print(f"   ✓ Change: {data.get('change')} ({data.get('changesPercentage')}%)")
            print(f"   ✓ Market Cap: {data.get('marketCap')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n📌 Test 3: Get AAPL Company Profile")
    try:
        profile = await get_company_profile("AAPL")
        print(f"   Response received: {type(profile)}")
        print(f"   Raw response: {profile}")  # Debug: print full response
        if isinstance(profile, dict):
            data = profile.get('data', profile)
            print(f"   ✓ Company: {data.get('companyName')}")
            print(f"   ✓ Industry: {data.get('industry')}")
            print(f"   ✓ Exchange: {data.get('exchange')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n📌 Test 4: Search Companies Realtime")
    try:
        search = await search_companies_realtime("Tesla", limit=3)
        print(f"   Response received: {type(search)}")
        if isinstance(search, dict):
            results = search.get('results', search.get('data', []))
            if isinstance(results, list):
                print(f"   ✓ Found {len(results)} results")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n📌 Test 5: Get TSLA Stock Data (combined realtime + historical)")
    try:
        tool = GetStockData()
        # Call _arun directly since we're already in async context
        result = await tool._arun(
            ticker_data=[TickerSchema(ticker="TSLA", exchange_symbol="NASDAQ")],
            explanation="Test",
            period="1M"
        )
        print(f"   Response received: {type(result)}")
        if result and len(result) > 0:
            item = result[0]
            print(f"   Full item: {item}")  # Debug: print full response
            if item.get('realtime'):
                rt = item['realtime']
                if 'error' not in rt:
                    print(f"   ✓ Realtime price: {rt.get('price')} (type: {type(rt.get('price'))})")
                    print(f"   ✓ Realtime change: {rt.get('change')} ({rt.get('changesPercentage')}%)")
                    print(f"   ✓ Market Cap: {rt.get('marketCap')}")
                else:
                    print(f"   ⚠️ Realtime error: {rt.get('error')}")
            if item.get('historical'):
                hist = item['historical']
                if 'error' not in hist:
                    print(f"   ✓ Historical data points: {len(hist.get('data', []))}")
                    if hist.get('data'):
                        first_point = hist['data'][0]
                        print(f"   ✓ First historical close: {first_point.get('close')} (type: {type(first_point.get('close'))})")
                else:
                    print(f"   ⚠️ Historical error: {hist.get('error')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
    
    
# uv run -m src.ai.tools.financial_tools