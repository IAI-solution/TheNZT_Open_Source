import asyncio
from asyncio.log import logger
from beanie import Document
import requests
from langchain_core.tools import tool, BaseTool
import os
import json
from datetime import datetime, timedelta
from datetime import timezone
import http.client
import tzlocal
import re, time
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Type, Dict, Union, Any
# from src.backend.db.qdrant import search_similar_company_name
from src.backend.utils.utils import pretty_format
import concurrent.futures
from .finance_scraper_utils import convert_fmp_to_json
from src.ai.ai_schemas.tool_structured_input import QueryRequest, SearchCompanyInfoSchema, CompanySymbolSchema, StockDataSchema, CombinedFinancialStatementSchema, CurrencyExchangeRateSchema, TickerSchema
import src.backend.db.mongodb as mongodb
from src.ai.tools.web_search_tools import AdvancedInternetSearchTool
# from crypto_data import get_crypto_data  
from tavily import TavilyClient
import yfinance as yf
import pandas as pd
import numpy as np


fm_api_key = os.getenv("FM_API_KEY")
currency_api_key = os.getenv("CURRENCY_FREAK_API_KEY")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


# class SearchCompanyInfoTool(BaseTool):
#     name: str = "search_company_info"
#     description: str = """
# Use this function to search for the ticker symbol or cryptocurrency symbol for financial instruments, including stocks, cryptocurrencies, forex, ETFs, etc. You can also pass the company name or cryptocurrency name. Multiple company or cryptocurrency names can be passed to this tool.
# If search for ticker symbol of companies then follow these rules for ticker symbol:
# - For USA based stock exchanges no suffix is required like TSLA will remain TSLA, APPL will remain APPL, etc.
# - For DFM stock exchange add .AE like DSI will become DSI.AE, DU will become DU.AE, etc.
# - For NSE stock exchange add .NS like TATAMOTORS will become TATAMOTORS.NS, RELIANCE will become RELIANCE.NS, etc.
# - For BSE stock exchange add .BO like TATAMOTORS will become TATAMOTORS.BO, RELIANCE will become RELIANCE.BO, etc.

# The `query` input parameter can be a list of company names, cryptocurrency names, or ticker symbols.
# """

#     args_schema: Type[BaseModel] = SearchCompanyInfoSchema
    
#     def _fetch_fmp_data(self, query: str) -> Union[List[Dict[str, Any]], str]:
#         try:
#             # url = f"https://financialmodelingprep.com/api/v3/search?query={query}&apikey={fm_api_key}"
#             url = f"https://financialmodelingprep.com/stable/search-name?query={query}&apikey={fm_api_key}"
#             fmp_response = requests.get(url)
#             return fmp_response.json()
#         except Exception as e:
#             return f"Error in getting company information from FMP for {query}: {str(e)}"
        
#     def search_company_sync(self, query: str, limit: int = 5) -> Union[Dict[str, Any], str]:
#         """
#         Synchronous wrapper: calls async vector/symbol search first,
#         falls back to FMP REST API if no results or error.
#         """
#         try:
#             result = search_similar_company_name(query, limit)
#             if result and result.get("results"):
#                 return result
#             else:
#                 logger.warning("Primary search returned empty. Falling back to FMP API.")
#                 #fallback_result = self._fetch_fmp_data(query)
#                 return {
#                     #"results": fallback_result,
#                     "source": "fmp",
#                     "timestamp": datetime.now().isoformat()
#                 }
#         except Exception as e:
#             logger.error(f"Primary async search failed: {str(e)}")
#             try:
#                 #fallback_result = self._fetch_fmp_data(query)
#                 return {
#                     #"results": fallback_result,
#                     "source": "fmp",
#                     "timestamp": datetime.now().isoformat()
#                 }
#             except Exception as fallback_error:
#                 return {
#                     "error": f"Both primary and fallback search failed. Reason: {str(fallback_error)}",
#                     "timestamp": datetime.now().isoformat()
#                 }
            
#     def _fetch_yf_data(self, query: str) -> Union[Dict[str, Any], str]:
#         try:
#             return fetch_company_info(query)  # Assuming this function is defined elsewhere
#         except Exception as e:
#             return f"Error in getting company information from YF for {query}: {str(e)}"

#     def _fetch_data_for_single_ticker(self, query: str) -> Dict[str, Any]:
#         fmp_data = self.search_company_sync(query)
#         yf_data = self._fetch_yf_data(query)
        
#         return {
#             "ticker": query,
#             "fmp_data": fmp_data, 
#             "yf_data": yf_data, 
#             "source": ["https://site.financialmodelingprep.com/", f"https://finance.yahoo.com/lookup/?s={query}"]
#         }

#     def _run(self, query: List[str], explanation: str) -> Dict[str, Any]:
        
#         results = []
#         with concurrent.futures.ThreadPoolExecutor(max_workers=len(query)) as executor:
#             # Submit tasks for each ticker
#             future_to_ticker = {executor.submit(self._fetch_data_for_single_ticker, ticker): ticker for ticker in query}
            
#             for future in concurrent.futures.as_completed(future_to_ticker):
#                 ticker = future_to_ticker[future]
#                 try:
#                     result = future.result()
#                     results.append(result)
#                 except Exception as e:
#                     results.append({
#                         "ticker": ticker,
#                         "error": f"Error processing {ticker}: {str(e)}",
#                         "fmp_data": None,
#                         "yf_data": None,
#                         "source": []
#                     })
        
#         return {"results": results}
class SearchCompanyInfoTool(BaseTool):
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

    If '&' is included in company name query, search for names containing '&' or replace it with 'and' and try both variations.
"""


    args_schema: Type[BaseModel] = SearchCompanyInfoSchema  
    def _fetch_fmp_data(self, query: str) -> Union[List[Dict[str, Any]], str]:
        try:
            url = f"https://financialmodelingprep.com/stable/search-name?query={query}&apikey={fm_api_key}"
            fmp_response = requests.get(url)
            return fmp_response.json()
        except Exception as e:
            return f"Error in getting company information from FMP for {query}: {str(e)}"
        
    # def search_company_sync(self, query: QueryRequest, limit: int = 5) -> Union[Dict[str, Any], str]:
    #     try:
    #         result = search_similar_company_name(query, limit)
    #         if result and result.get("results"):
    #             return result
    #         else:
    #             logger.warning("Primary search returned empty. Falling back to FMP API.")
    #             return {
    #                 "source": "fmp",
    #                 "timestamp": datetime.now().isoformat()
    #             }
    #     except Exception as e:
    #         logger.error(f"Primary search failed: {str(e)}")
    #         try:
    #             return {
    #                 "source": "fmp",
    #                 "timestamp": datetime.now().isoformat()
    #             }
    #         except Exception as fallback_error:
    #             return {
    #                 "error": f"Both primary and fallback search failed. Reason: {str(fallback_error)}",
    #                 "timestamp": datetime.now().isoformat()
    #             }
            
    # def _fetch_yf_data(self, query: str) -> Union[Dict[str, Any], str]:
    #     try:
    #         return fetch_company_info(query)  # Assuming this function is defined elsewhere
    #     except Exception as e:
    #         return f"Error in getting company information from YF for {query}: {str(e)}"

    def _fetch_data_for_single_ticker(self, query_request: QueryRequest) -> Dict[str, Any]:
       
       fmp_data = self._fetch_fmp_data(query_request.query)       
       return {
           "query": query_request.query,
           "type": query_request.type,
           "exchange_short_name": query_request.exchange_short_name,
           "fmp_data": fmp_data,
           "source": [
               "https://site.financialmodelingprep.com/",
               f"https://finance.yahoo.com/lookup/?s={query_request.query}"
           ]
       }

    def _run(self, query_list: List[QueryRequest], explanation: str) -> Dict[str, Any]:
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(query_list)) as executor:
            future_to_query = {
                executor.submit(self._fetch_data_for_single_ticker, query_obj): query_obj
                for query_obj in query_list
            }


            for future in concurrent.futures.as_completed(future_to_query):
                query_obj = future_to_query[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "query": query_obj.query,
                        "type": query_obj.type,
                        "exchange_short_name": query_obj.exchange_short_name,
                        "error": f"Error processing {query_obj.query}: {str(e)}",
                        "fmp_data": None,
                        "yf_data": None,
                        "source": []
                    })


        return {"results": results}


class CompanyProfileTool(BaseTool):
    name: str = "get_usa_based_company_profile"
    description: str = """Use this tool to get company profile information through its ticker symbol.
This tool provides information of companies registered."""
    args_schema: Type[BaseModel] = CompanySymbolSchema

    def _run(self, symbol: str, explanation: str):
        try:
            #url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={fm_api_key}"
            #response = requests.get(url)
            response=mongodb.get_or_fetch_company_profile(symbol)
            # return pretty_format(response.json()) + "\n\n- Source: https://site.financialmodelingprep.com/"
            #return {"data": response.json(), "source": "https://site.financialmodelingprep.com/"}
            return response
        except Exception as e:
            error_msg = f"Error in getting company profile information: {str(e)}"
            return error_msg


# class GetStockData(BaseTool):
#     name: str = "get_stock_data"
#     description: str = """Use this tool to get real-time stock quote data and historical stock prices of companies. The realtime stock data includes price, changes, market cap, PE ratio, and more.
#     This tool generates a stock price chart which is only visible to the user.
# """
#     args_schema: Type[BaseModel] = StockDataSchema

#     def _run(self, ticker_data: List[TickerSchema], explanation: str = None, period: str = "1M", strictly: bool = False):
#         def process_ticker(ticker_info):
#             ticker = ticker_info.ticker
#             exchange_symbol = ticker_info.exchange_symbol
#             result = {"realtime": None, "historical": None}

#             # Fetch Real-Time Data
#             try:
#                 if exchange_symbol and ticker:
#                     try:
#                         # url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={fm_api_key}"
#                         url = f"https://financialmodelingprep.com/stable/quote/?symbol={ticker}&apikey={fm_api_key}"
#                         currency_url = f'https://financialmodelingprep.com/stable/search-symbol?query={ticker}&apikey={fm_api_key}'
#                         data = requests.get(url)
#                         currency_data = requests.get(currency_url).json()
#                         realtime_response = data.json()
#                         realtime_currency = currency_data[0]["currency"] if currency_data else "USD"
#                         realtime_response[0]["currency"] = realtime_currency
#                         realtime_response = realtime_response[0]
#                         realtime_response = {k: v for k, v in realtime_response.items() if v is not None}
#                     except Exception as e:
#                         realtime_response = {"error": f"Error fetching realtime data from FMP: {str(e)}. Use web search tool for current stock prices."}
#                 else:
#                     realtime_response = {"error": "Use web search tool for data not available from FMP."}                 

#                 result["realtime"] = realtime_response
#             except Exception as e:
#                 result["realtime"] = {"error": f"Failed to get realtime data: {str(e)}"}

#             try:
#                 periods = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]   

#                 if exchange_symbol and ticker:
#                     try:
#                         historical_data = None
#                         successful_period_index = None
#                         if not strictly:
#                             for i, p in enumerate(periods):
#                                 print(f"Trying period: {p}")
#                                 historical_data = mongodb.get_or_update_historical(ticker, p)
                                
#                                 if historical_data and len(historical_data) > 0:
#                                     successful_period_index = i
#                                     print(f"Data found for period: {p}")
#                                     break
#                                 else:
#                                     print(f"No data found for period: {p}")
#                         else:
#                             historical_data = mongodb.get_or_update_historical(ticker, period)

#                         if 'historical' in historical_data and historical_data['historical']:
#                             result["historical"] = {"source": "https://financialmodelingprep.com/"}
#                             if strictly:
#                                 result["historical"]["period"] = period
#                             else:
#                                 result["historical"]["period"]  = periods[successful_period_index:]

#                             raw_data = historical_data['historical']
#                             formatted_data = convert_fmp_to_json(raw_data, ticker)
#                         else:
#                             raise RuntimeError("No data available after filtering")

#                         result["historical"]["data"] = formatted_data
#                         # Check last 5 days activity
#                         today = datetime.now().date()

#                         # Get the last entry assuming it's the most recent date
#                         data_list = []
#                         if isinstance(historical_data, dict):
#                             data_list = historical_data.get("historical", []) or historical_data.get("data", [])
#                         elif isinstance(historical_data, list):
#                             data_list = historical_data

#                         # Take the last available record
#                         last_entry = data_list[0] if data_list else None

#                         if last_entry:
#                             date_str = last_entry.get("date", "")
#                             try:
#                                 if "-" in date_str:
#                                     last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
#                                 else:
#                                     last_date = datetime.strptime(date_str, "%b %d, %Y").date()

#                                 days_diff = (today - last_date).days
#                                 result["historical"]["is_active"] = False if days_diff > 5 else True
#                             except Exception:
#                                 result["historical"]["is_active"] = False
#                         else:
#                             result["historical"]["is_active"] = False

                        

#                     except Exception as e:
#                         result["historical"] = {
#                             "error": f"Error fetching historical data from FMP: {str(e)}. Use web search tool for historical stock data.",
#                             "data": [],
#                             "source": "FMP API failed"
#                         }                       
#                 else:
#                     historical_data = {"error": "Use web search tool for data not available from FMP."}
#             except Exception as e:
#                 error_msg = f"Stock history scrapping error: {e}"
#                 print(error_msg)
#                 result["historical"] = {"error": error_msg}
    
#             if (not 'error' in result['historical']) and (not 'error' in result['realtime']):
#                 result['message'] = "A graph has been generated and shown to the user so do not include this data in the response."
#             else:
#                 result['message'] = "Generate a graph based on this data which is visible to the user."
#             return result
        
#         all_results = []
#         with concurrent.futures.ThreadPoolExecutor(max_workers=len(ticker_data)) as executor:
#             future_to_ticker = {executor.submit(process_ticker, ticker_info): ticker_info for ticker_info in ticker_data}
#             for future in concurrent.futures.as_completed(future_to_ticker):
#                 ticker_info = future_to_ticker[future]
#                 try:
#                     result = future.result()
#                     all_results.append(result)
#                 except Exception as e:
#                     error_msg = f"Processing of {ticker_info.ticker} generated an exception: {str(e)}"
#                     print(error_msg)

#         return all_results


# class GetStockData(BaseTool):
#     name: str = "get_stock_data"
#     description: str = """Use this tool to get real-time stock quote data and historical stock prices of companies. The realtime stock data includes price, changes, market cap, PE ratio, and more.
#     This tool generates a stock price chart which is only visible to the user.
#     """
#     args_schema: Type[BaseModel] = StockDataSchema

#     _YF_PERIOD_MAP = {
#         "1M": "1mo",
#         "3M": "3mo",
#         "6M": "6mo",
#         "YTD": "ytd",
#         "1Y": "1y",
#         "5Y": "5y",
#         "MAX": "max"
#     }
    
#     def _candidate_yf_tickers(self, ticker: str, exchange_symbol: Optional[str]) -> List[str]:
#         if not ticker:
#             return []
#         candidates = [ticker]
#         base = ticker
#         for suf in [".NS", ".BO", ".L", ".SA", ".TO", ".AX", ".TW"]:
#             if ticker.endswith(suf):
#                 base = ticker[: -len(suf)]
#                 break
#         if exchange_symbol:
#             exch = exchange_symbol.upper()
#             if exch == "NSE" and f"{base}.NS" not in candidates:
#                 candidates.append(f"{base}.NS")
#             if exch == "BSE" and f"{base}.BO" not in candidates:
#                 candidates.append(f"{base}.BO")
#             if base not in candidates:
#                 candidates.append(base)
#         else:
#             for suf in [".NS", ".BO"]:
#                 variant = f"{base}{suf}"
#                 if variant not in candidates:
#                     candidates.append(variant)
#             if base not in candidates:
#                 candidates.append(base)
        
#         seen = set()
#         out = []
#         for c in candidates:
#             if c not in seen:
#                 seen.add(c)
#                 out.append(c)
#         return out

#     def _yf_realtime(self, ticker: str) -> dict:
#         t = yf.Ticker(ticker)
#         price = None
#         ts = None
#         used = None

#         # intraday stock history 
#         try:
#             for intraday_period, intraday_interval in (("1d", "1m"), ("5d", "5m")):
#                 try:
#                     hist = t.history(period=intraday_period, interval=intraday_interval, actions=False)
#                     if hist is not None and not hist.empty:
#                         if isinstance(hist, pd.Series):
#                             hist = hist.to_frame().T
#                         last = hist.iloc[-1]
#                         price_candidate = last.get("Close", None) or last.get("close", None)
#                         if price_candidate is not None and not pd.isna(price_candidate):
#                             price = float(price_candidate)
#                             idx = last.name
#                             ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
#                             used = f"history({intraday_period},{intraday_interval})"
#                             break
#                 except Exception:
#                     continue
#         except Exception:
#             pass

#         # multi-day
#         if price is None:
#             try:
#                 hist2 = t.history(period="7d", interval="1d", actions=False)
#                 if hist2 is not None and not hist2.empty:
#                     if isinstance(hist2, pd.Series):
#                         hist2 = hist2.to_frame().T
#                     last = hist2.iloc[-1]
#                     pc = last.get("Close", None) or last.get("close", None)
#                     if pc is not None and not pd.isna(pc):
#                         price = float(pc)
#                         idx = last.name
#                         ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
#                         used = "history(7d,1d)"
#             except Exception:
#                 pass

#         if price is None:
#             try:
#                 fi = getattr(t, "fast_info", None)
#                 if fi:
#                     for k in ("lastPrice", "last_trade_price", "last_price", "last"):
#                         if isinstance(fi, dict) and fi.get(k) is not None:
#                             price = float(fi[k])
#                             used = f"fast_info[{k}]"
#                             break
#                     if price is None:
#                         try:
#                             if hasattr(fi, "get") and fi.get("lastPrice"):
#                                 price = float(fi.get("lastPrice"))
#                                 used = "fast_info[lastPrice]"
#                         except Exception:
#                             pass
#             except Exception:
#                 pass

#         # fallback
#         info = {}
#         try:
#             info = t.info or {}
#         except Exception:
#             info = {}

#         if price is None:
#             try:
#                 cand = info.get("regularMarketPrice") or info.get("previousClose") or info.get("currentPrice") or info.get("price")
#                 if cand is not None and not pd.isna(cand):
#                     try:
#                         price = float(cand)
#                         used = "info"
#                     except Exception:
#                         price = None
#             except Exception:
#                 pass

#         # timestamp fallback
#         if not ts:
#             try:
#                 rmt = info.get("regularMarketTime") or info.get("regularMarketPreviousCloseTime")
#                 if isinstance(rmt, (int, float)):
#                     try:
#                         ts = datetime.fromtimestamp(int(rmt), tz=timezone.utc).isoformat()
#                     except Exception:
#                         ts = None
#             except Exception:
#                 ts = None
#         if not ts:
#             ts = datetime.now(timezone.utc).isoformat()

#         change = None
#         marketCap = None
#         currency = None
#         try:
#             change = info.get("regularMarketChange") or info.get("change")
#         except Exception:
#             change = None
#         try:
#             marketCap = info.get("marketCap")
#         except Exception:
#             marketCap = None
#         try:
#             currency = info.get("currency") or (info.get("currency_symbol") if info.get("currency_symbol") else None)
#         except Exception:
#             currency = None

#         # attach a company name (for streaming to frontend)
#         name = None
#         try:
#             for k in ("shortName", "longName", "name"):
#                 cand = info.get(k)
#                 if cand:
#                     name = cand
#                     break
#             if not name and isinstance(info.get("longBusinessSummary"), str):
#                 name = info.get("longBusinessSummary")[:200]
#         except Exception:
#             name = None

#         realtime = {
#             "symbol": ticker,
#             "price": price if price is not None else None,
#             "change": change if change is not None else None,
#             "marketCap": marketCap if marketCap is not None else None,
#             "currency": currency if currency is not None else "USD",
#             "timestamp": ts,
#             "_yf_used": used or "none"
#         }

#         if name:
#             realtime["name"] = name
#             realtime["companyName"] = name

#         return {k: v for k, v in realtime.items() if v is not None}

#     # helpers for historical formatting
#     def _to_str_num(self, v, pick_key=None):
#         """
#         Return (string_value, numeric_value) for v. If v is Series/array/list pick first non-null.
#         """
#         try:
#             if isinstance(v, (pd.Series, pd.DataFrame)):
#                 if isinstance(v, pd.DataFrame):
#                     v = v.iloc[:, 0]
#                 if pick_key is not None and isinstance(v, pd.Series) and pick_key in v.index:
#                     val = v[pick_key]
#                 else:
#                     try:
#                         val = v.dropna().iloc[0]
#                     except Exception:
#                         val = v.iloc[0] if len(v) > 0 else None
#                 v = val
#             if isinstance(v, (list, tuple, np.ndarray)):
#                 # pick first non-null
#                 v = next((x for x in v if x is not None and not (isinstance(x, float) and np.isnan(x))), None)
#             if hasattr(v, "item"):
#                 try:
#                     v = v.item()
#                 except Exception:
#                     pass
#             if v is None or pd.isna(v):
#                 return None, None
#             if isinstance(v, (int, float, np.integer, np.floating)):
#                 s = ("{:.8f}".format(float(v))).rstrip("0").rstrip(".")
#                 return s, float(v)
#             if isinstance(v, str):
#                 vs = v.replace(",", "").strip()
#                 try:
#                     n = float(vs)
#                     s = ("{:.8f}".format(n)).rstrip("0").rstrip(".")
#                     return s, n
#                 except Exception:
#                     return v, None
#             try:
#                 n = float(v)
#                 s = ("{:.8f}".format(n)).rstrip("0").rstrip(".")
#                 return s, n
#             except Exception:
#                 return str(v), None
#         except Exception:
#             try:
#                 return str(v), None
#             except Exception:
#                 return None, None

#     def _fmt_vol(self, v, pick_key=None):
#         try:
#             if isinstance(v, (pd.Series, pd.DataFrame)):
#                 if isinstance(v, pd.DataFrame):
#                     v = v.iloc[:, 0]
#                 if pick_key is not None and isinstance(v, pd.Series) and pick_key in v.index:
#                     v = v[pick_key]
#                 else:
#                     try:
#                         v = v.dropna().iloc[0]
#                     except Exception:
#                         v = v.iloc[0] if len(v) > 0 else None
#             if isinstance(v, (list, tuple, np.ndarray)):
#                 v = next((x for x in v if x is not None and not (isinstance(x, float) and np.isnan(x))), None)
#             if v is None or pd.isna(v):
#                 return None
#             return int(float(str(v).replace(",", "")))
#         except Exception:
#             return None

#     def _safe_date_val(self, val, fallback=None):
#         try:
#             if isinstance(val, (pd.Series, pd.DataFrame)):
#                 if isinstance(val, pd.DataFrame):
#                     val = val.iloc[:, 0]
#                 try:
#                     val = val.dropna().iloc[0]
#                 except Exception:
#                     try:
#                         val = val.iloc[0]
#                     except Exception:
#                         val = fallback
#             if isinstance(val, (list, tuple, np.ndarray)):
#                 val = next((x for x in val if x is not None and not (isinstance(x, float) and np.isnan(x))), fallback)
#             if val is None:
#                 val = fallback
#             if hasattr(val, "strftime"):
#                 return val.strftime("%b %d, %Y")
#             parsed = pd.to_datetime(val, errors="coerce")
#             if parsed is pd.NaT or parsed is None:
#                 return str(val) if val is not None else ""
#             return parsed.strftime("%b %d, %Y")
#         except Exception:
#             try:
#                 return str(val)
#             except Exception:
#                 return ""

#     def _extract_ticker_subframe(self, df, requested_ticker):
#         """
#         If df has MultiIndex columns because yf.download returned multiple tickers,
#         attempt to extract the subframe for requested_ticker.
#         """
#         try:
#             if not isinstance(df, pd.DataFrame):
#                 return df
#             if isinstance(df.columns, pd.MultiIndex):
#                 cols = df.columns
#                 base = requested_ticker.split(".")[0] if "." in requested_ticker else requested_ticker
#                 candidates = [requested_ticker, base]
#                 for level in [1, 0]:
#                     labels = [str(x) for x in cols.get_level_values(level)]
#                     for cand in candidates:
#                         if cand in labels:
#                             try:
#                                 sub = df.xs(cand, axis=1, level=level, drop_level=True)
#                                 return sub
#                             except Exception:
#                                 try:
#                                     sub = df.loc[:, df.columns.get_level_values(level) == cand]
#                                     if isinstance(sub.columns, pd.MultiIndex):
#                                         sub.columns = sub.columns.droplevel(level)
#                                     return sub
#                                 except Exception:
#                                     continue
#                 # fallback: return first ticker group if nothing matches
#                 try:
#                     lvl1 = list(dict.fromkeys(df.columns.get_level_values(1)))
#                     if lvl1:
#                         sub = df.xs(lvl1[0], axis=1, level=1, drop_level=True)
#                         return sub
#                 except Exception:
#                     pass
#             return df
#         except Exception:
#             return df

#     # historical attempts
#     def _yf_historical_try_methods(self, ticker: str, desired_period: str) -> dict:
#         """
#         Returns {"historical": [...]} where each record: date (e.g. 'Sep 16, 2025'),
#         open, open_num, high, high_num, low, low_num, close, close_num, volume, ticker
#         newest-first.
#         """
#         yf_period = self._YF_PERIOD_MAP.get(desired_period, "1mo")

#         # yf.download
#         try:
#             df = yf.download(ticker, period=yf_period, progress=False, threads=False, auto_adjust=False)
#             if df is not None and not df.empty:
#                 df = self._extract_ticker_subframe(df, ticker)
#                 if df is not None and not df.empty:
#                     if isinstance(df, pd.Series):
#                         df = df.to_frame().T
#                     df = df.reset_index()
#                     out = []
#                     for _, row in df.iterrows():
#                         date_val = row.get("Date", getattr(row, "name", None))
#                         date_str = self._safe_date_val(date_val, fallback=row.name)
#                         open_s, open_n = self._to_str_num(row.get("Open") if "Open" in row else row.get("open"))
#                         high_s, high_n = self._to_str_num(row.get("High") if "High" in row else row.get("high"))
#                         low_s, low_n = self._to_str_num(row.get("Low") if "Low" in row else row.get("low"))
#                         close_s, close_n = self._to_str_num(row.get("Close") if "Close" in row else row.get("close"))
#                         vol_i = self._fmt_vol(row.get("Volume") if "Volume" in row else row.get("volume"))
#                         out.append({
#                             "date": date_str,
#                             "open": open_s,
#                             "open_num": open_n,
#                             "high": high_s,
#                             "high_num": high_n,
#                             "low": low_s,
#                             "low_num": low_n,
#                             "close": close_s,
#                             "close_num": close_n,
#                             "volume": vol_i,
#                             "ticker": ticker
#                         })
#                     # out = list(reversed(out))  
#                     return {"historical": out}
#         except Exception as e:
#             print(f"[DEBUG] yf.download failed for {ticker} period={yf_period}: {e}")

#         # ticker.history
#         try:
#             t = yf.Ticker(ticker)
#             end = datetime.now()
#             days_map = {"1M": 30, "3M": 90, "6M": 180, "YTD": 365, "1Y": 365, "5Y": 365*5, "MAX": 365*20}
#             days = days_map.get(desired_period, 30)
#             start = end - timedelta(days=days)
#             df2 = t.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval="1d", actions=False)
#             if df2 is not None and not df2.empty:
#                 df2 = self._extract_ticker_subframe(df2, ticker)
#                 if isinstance(df2, pd.Series):
#                     df2 = df2.to_frame().T
#                 df2 = df2.reset_index()
#                 out = []
#                 for _, row in df2.iterrows():
#                     date_val = row.get("Date", getattr(row, "name", None))
#                     date_str = self._safe_date_val(date_val, fallback=row.name)
#                     open_s, open_n = self._to_str_num(row.get("Open") if "Open" in row else row.get("open"))
#                     high_s, high_n = self._to_str_num(row.get("High") if "High" in row else row.get("high"))
#                     low_s, low_n = self._to_str_num(row.get("Low") if "Low" in row else row.get("low"))
#                     close_s, close_n = self._to_str_num(row.get("Close") if "Close" in row else row.get("close"))
#                     vol_i = self._fmt_vol(row.get("Volume") if "Volume" in row else row.get("volume"))
#                     out.append({
#                         "date": date_str,
#                         "open": open_s,
#                         "open_num": open_n,
#                         "high": high_s,
#                         "high_num": high_n,
#                         "low": low_s,
#                         "low_num": low_n,
#                         "close": close_s,
#                         "close_num": close_n,
#                         "volume": vol_i,
#                         "ticker": ticker
#                     })
#                 # out = list(reversed(out))
#                 return {"historical": out}
#         except Exception as e:
#             print(f"[DEBUG] Ticker.history failed for {ticker}: {e}")

#         return {"historical": []}

#     def _try_yf_multi_periods(self, ticker: str, desired_period: str = "1M"):
#         period_seq = []
#         if desired_period and desired_period in self._YF_PERIOD_MAP:
#             period_seq.append(desired_period)
#         fallback_order = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]
#         for p in fallback_order:
#             if p not in period_seq:
#                 period_seq.append(p)
#         for p in period_seq:
#             try:
#                 hist = self._yf_historical_try_methods(ticker, p)
#                 lst = hist.get("historical") or []
#                 if lst:
#                     return (p, lst)
#             except Exception as e:
#                 print(f"[_try_yf_multi_periods] yfinance failed for {ticker} period {p}: {e}")
#                 continue
#         return (None, [])

#     def _fetch_historical_from_yf_and_format(self, ticker: str, desired_period: str = "1M"):
#         res = self._yf_historical_try_methods(ticker, desired_period).get("historical", []) or []
#         return res if res else None

#     def _normalize_historical_payload(self, historical_data):
#         if not historical_data:
#             return None
#         if isinstance(historical_data, list):
#             return historical_data if historical_data else None
#         if isinstance(historical_data, dict):
#             for key in ("historical", "data", "rows", "results"):
#                 if key in historical_data and isinstance(historical_data[key], list) and historical_data[key]:
#                     return historical_data[key]
#             for v in historical_data.values():
#                 if isinstance(v, list) and v:
#                     return v
#         return None

#     def _ensure_newest_first(self, lst):
#         if not lst:
#             return lst
#         try:
#             return sorted(lst, key=lambda r: pd.to_datetime(r.get("date")), reverse=True)
#         except Exception:
#             return lst

#     # main runner 
#     def _run(self, ticker_data: List[TickerSchema], explanation: str = None, period: str = "1M", strictly: bool = False):
#         def process_ticker(ticker_info):
#             ticker = getattr(ticker_info, "ticker", None)
#             exchange_symbol = getattr(ticker_info, "exchange_symbol", None)
#             result = {"realtime": None, "historical": None}

#             # Realtime (FMP -> yfinance fallback)
#             realtime_response = None
#             try:
#                 if exchange_symbol and ticker:
#                     try:
#                         url = f"https://financialmodelingprep.com/stable/quote/?symbol={ticker}&apikey={fm_api_key}"
#                         currency_url = f'https://financialmodelingprep.com/stable/search-symbol?query={ticker}&apikey={fm_api_key}'
#                         data_resp = requests.get(url, timeout=10)
#                         search_resp = requests.get(currency_url, timeout=8)
#                         if data_resp.ok:
#                             fmp_json = data_resp.json()
#                         else:
#                             print(f"[DEBUG] FMP realtime status {data_resp.status_code} for {ticker}")
#                             fmp_json = None
#                         if isinstance(fmp_json, list) and len(fmp_json) > 0 and isinstance(fmp_json[0], dict):
#                             realtime_response = dict(fmp_json[0])
#                             if search_resp.ok:
#                                 currency_json = search_resp.json()
#                                 if isinstance(currency_json, list) and len(currency_json) > 0 and isinstance(currency_json[0], dict):
#                                     realtime_response["currency"] = currency_json[0].get("currency", realtime_response.get("currency", "USD"))
#                                 else:
#                                     realtime_response.setdefault("currency", realtime_response.get("currency", "USD"))
#                             else:
#                                 realtime_response.setdefault("currency", realtime_response.get("currency", "USD"))
#                         else:
#                             cand = self._candidate_yf_tickers(ticker, exchange_symbol)
#                             for c in cand:
#                                 try:
#                                     rt = self._yf_realtime(c)
#                                     if rt and rt.get("price") is not None:
#                                         realtime_response = rt
#                                         break
#                                 except Exception:
#                                     continue
#                             if realtime_response is None:
#                                 realtime_response = {"error": "Failed to fetch realtime from FMP and yfinance."}
#                     except Exception as e_fmp_rt:
#                         print(f"[DEBUG] FMP realtime exception for {ticker}: {e_fmp_rt}")
#                         realtime_response = self._yf_realtime(ticker)
#                 else:
#                     realtime_response = {"error": "Use web search tool for data not available from FMP."}
#             except Exception as e:
#                 realtime_response = {"error": f"Failed to get realtime data: {str(e)}"}

#             # ensure symbol/timestamp/companyName exist
#             if isinstance(realtime_response, dict) and "symbol" not in realtime_response:
#                 realtime_response["symbol"] = ticker
#             if isinstance(realtime_response, dict):
#                 if "timestamp" not in realtime_response or not realtime_response.get("timestamp"):
#                     realtime_response["timestamp"] = datetime.now(timezone.utc).isoformat()
#                 if "companyName" not in realtime_response and "name" in realtime_response:
#                     realtime_response["companyName"] = realtime_response.get("name")
#             result["realtime"] = {k: v for k, v in (realtime_response or {}).items() if v is not None}

#             # Historical: try DB/FMP -> if 402 fallback to yfinance (and upsert optionally)
#             try:
#                 periods = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]
#                 historical_data = None
#                 successful_period_index = None
#                 fmp_payment_required = False

#                 if exchange_symbol and ticker:
#                     try:
#                         if not strictly:
#                             for i, p in enumerate(periods):
#                                 try:
#                                     hist = mongodb.get_or_update_historical(ticker, p)
#                                     print(f"[DEBUG] mongodb.get_or_update_historical({ticker}, {p}) returned type={type(hist)}")
#                                     normalized = self._normalize_historical_payload(hist)
#                                     if normalized:
#                                         historical_data = normalized
#                                         successful_period_index = i
#                                         break
#                                 except Exception as e_db:
#                                     txt = str(e_db).lower()
#                                     print(f"[ERROR] mongodb fetch failed for {ticker}: {e_db}")
#                                     if "402" in txt or "payment required" in txt or ("payment" in txt and "required" in txt):
#                                         print(f"[WARN] Detected FMP payment required for {ticker}; falling back to yfinance.")
#                                         fmp_payment_required = True
#                                         historical_data = None
#                                         break
#                                     else:
#                                         continue
#                         else:
#                             try:
#                                 hist = mongodb.get_or_update_historical(ticker, period)
#                                 historical_data = self._normalize_historical_payload(hist)
#                             except Exception as e_db:
#                                 txt = str(e_db).lower()
#                                 print(f"[ERROR] strict mongodb fetch failed: {e_db}")
#                                 if "402" in txt or "payment required" in txt:
#                                     fmp_payment_required = True
#                                     historical_data = None
#                                 else:
#                                     historical_data = None
#                     except Exception as e_db_outer:
#                         print(f"[ERROR] mongodb outer exception for {ticker}: {e_db_outer}")
#                         historical_data = None
#                 else:
#                     historical_data = None

#                 if historical_data:
#                     try:
#                         formatted_data = convert_fmp_to_json(historical_data, ticker)
#                     except Exception as e_conv:
#                         print(f"[WARN] convert_fmp_to_json failed for {ticker}: {e_conv}; using passthrough normalized data")
#                         formatted_data = self._ensure_newest_first(historical_data)
#                     formatted_data = self._ensure_newest_first(formatted_data)
#                     result["historical"] = {"source": "https://financialmodelingprep.com/"}
#                     result["historical"]["period"] = period if strictly else periods[successful_period_index:]
#                     result["historical"]["data"] = formatted_data
#                 else:
#                     yf_success = False
#                     candidates = self._candidate_yf_tickers(ticker, exchange_symbol)
#                     for cand in candidates:
#                         chosen_period, yf_list = self._try_yf_multi_periods(cand, desired_period=period if strictly else "1M")
#                         if yf_list:
#                             # normalise records for frontend expectations
#                             for rec in yf_list:
#                                 rec.setdefault("ticker", ticker)
#                                 try:
#                                     dt = pd.to_datetime(rec.get("date"), errors="coerce")
#                                     if not pd.isna(dt):
#                                         rec["date"] = dt.strftime("%b %d, %Y")
#                                 except Exception:
#                                     pass
#                                 if ("open" not in rec or rec.get("open") is None) and rec.get("open_num") is not None:
#                                     rec["open"] = ("{:.8f}".format(rec["open_num"])).rstrip("0").rstrip(".")
#                                 if ("high" not in rec or rec.get("high") is None) and rec.get("high_num") is not None:
#                                     rec["high"] = ("{:.8f}".format(rec["high_num"])).rstrip("0").rstrip(".")
#                                 if ("close" not in rec or rec.get("close") is None) and rec.get("close_num") is not None:
#                                     rec["close"] = ("{:.8f}".format(rec["close_num"])).rstrip("0").rstrip(".")
#                             result["historical"] = {"source": "yfinance", "period": chosen_period or (period if strictly else "1M"), "data": yf_list}
#                             yf_success = True
#                             break

#                     # final fallback explicit fetch & format
#                     if not yf_success:
#                         fallback_data = self._fetch_historical_from_yf_and_format(ticker, period if strictly else "1M")
#                         if fallback_data:
#                             result["historical"] = {"source": "yfinance", "period": (period if strictly else "1M"), "data": fallback_data}
#                             try:
#                                 if hasattr(mongodb, "upsert_historical_raw"):
#                                     try:
#                                         mongodb.upsert_historical_raw(ticker, fallback_data, source="yfinance")
#                                     except Exception:
#                                         pass
#                             except Exception:
#                                 pass
#                             yf_success = True

#                     if not yf_success:
#                         result["historical"] = {"error": "No data available after filtering", "data": [], "source": "FMP+yfinance failed"}
#             except Exception as e:
#                 print(f"[ERROR] historical section failed for {ticker}: {e}")
#                 result["historical"] = {"error": f"Stock history scrapping error: {e}", "data": [], "source": None}

#             # is_active
#             try:
#                 data_list = []
#                 if isinstance(result.get("historical"), dict):
#                     data_list = result["historical"].get("data", []) or []
#                 elif isinstance(result.get("historical"), list):
#                     data_list = result["historical"]
#                 last_entry = data_list[0] if data_list else None
#                 if last_entry:
#                     date_str = last_entry.get("date", "")
#                     try:
#                         if "-" in date_str:
#                             last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
#                         else:
#                             last_date = datetime.strptime(date_str, "%b %d, %Y").date()
#                         days_diff = (datetime.now().date() - last_date).days
#                         result["historical"]["is_active"] = False if days_diff > 5 else True
#                     except Exception:
#                         result["historical"]["is_active"] = False
#                 else:
#                     if isinstance(result.get("historical"), dict):
#                         result["historical"]["is_active"] = False
#             except Exception:
#                 if isinstance(result.get("historical"), dict):
#                     result["historical"]["is_active"] = False
#                 else:
#                     result["historical"] = {"error": "is_active check failed", "data": result.get("historical", {})}

#             try:
#                 if (not isinstance(result.get('historical', {}), dict) or 'error' not in result['historical']) and (not isinstance(result.get('realtime', {}), dict) or 'error' not in result['realtime']):
#                     result['message'] = "A graph has been generated and shown to the user so do not include this data in the response."
#                 else:
#                     result['message'] = "Generate a graph based on this data which is visible to the user."
#             except Exception:
#                 result['message'] = "Generate a graph based on this data which is visible to the user."

#             return result

#         all_results = []
#         if not ticker_data:
#             return all_results
#         with concurrent.futures.ThreadPoolExecutor(max_workers=len(ticker_data)) as executor:
#             future_to_ticker = {executor.submit(process_ticker, ticker_info): ticker_info for ticker_info in ticker_data}
#             for future in concurrent.futures.as_completed(future_to_ticker):
#                 ticker_info = future_to_ticker[future]
#                 try:
#                     res = future.result()
#                     if not isinstance(res, dict):
#                         res = {"realtime": {"symbol": getattr(ticker_info, "ticker", "unknown"), "timestamp": datetime.now(timezone.utc).isoformat()}, "historical": {"data": []}, "message": "Generate a graph based on this data which is visible to the user."}
#                     if "historical" not in res or not isinstance(res["historical"], dict):
#                         res.setdefault("historical", {"data": []})
#                     if "data" not in res["historical"]:
#                         res["historical"].setdefault("data", [])
#                     all_results.append(res)
#                 except Exception as e:
#                     print(f"[ERROR] processing worker failed: {e}")
#                     fallback = {"realtime": {"symbol": getattr(ticker_info, "ticker", "unknown"), "timestamp": datetime.now(timezone.utc).isoformat()}, "historical": {"data": [], "error": str(e)}, "message": "Generate a graph based on this data which is visible to the user."}
#                     all_results.append(fallback)
#         return all_results

class GetStockData(BaseTool):
    name: str = "get_stock_data"
    description: str = """Use this tool to get real-time stock quote data and historical stock prices of companies.
    This tool generates a stock price chart which is only visible to the user.
    """
    args_schema: Type[BaseModel] = StockDataSchema  

    _YF_PERIOD_MAP = {
        "1M": "1mo",
        "3M": "3mo",
        "6M": "6mo",
        "YTD": "ytd",
        "1Y": "1y",
        "5Y": "5y",
        "MAX": "max"
    }

    def _candidate_yf_tickers(self, ticker: str, exchange_symbol: Optional[str]) -> List[str]:
        if not ticker:
            return []
        candidates = []
        base = ticker
        for suf in [".NS", ".BO", ".L", ".SA", ".TO", ".AX", ".TW", ".AE"]:
            if ticker.endswith(suf):
                base = ticker[: -len(suf)]
                break

        candidates.append(ticker)
        if exchange_symbol:
            exch = exchange_symbol.upper()
            if exch == "NSE":
                candidates.append(f"{base}.NS")
            elif exch == "BSE":
                candidates.append(f"{base}.BO")
            elif exch == "DFM":
                candidates.append(f"{base}.AE")
            else:
                candidates.extend([f"{base}.NS", f"{base}.BO", base])
        else:
            candidates.extend([f"{base}.NS", f"{base}.BO", base])

        seen = set()
        out = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _yf_realtime(self, ticker: str) -> dict:
        """Fetch realtime data including Open, High, Low, Close, Volume, PE Ratio from yfinance"""
        t = yf.Ticker(ticker)

        price = None
        open_price = None
        high_price = None
        low_price = None
        volume = None
        year_high = None
        year_low = None
        ts = None
        used = None

        # Try intraday then 7d/5d daily
        try:
            for intraday_period, intraday_interval in (("1d", "1m"), ("5d", "5m")):
                try:
                    hist = t.history(period=intraday_period, interval=intraday_interval, actions=False)
                    if hist is not None and not hist.empty:
                        if isinstance(hist, pd.Series):
                            hist = hist.to_frame().T
                        last = hist.iloc[-1]
                        close_candidate = last.get("Close", None) or last.get("close", None)
                        if close_candidate is not None and not pd.isna(close_candidate):
                            price = float(close_candidate)
                            idx = last.name
                            ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                            used = f"history({intraday_period},{intraday_interval})"
                            break
                except Exception:
                    continue
        except Exception:
            pass

        # multi-day daily
        if price is None:
            try:
                hist2 = t.history(period="7d", interval="1d", actions=False)
                if hist2 is not None and not hist2.empty:
                    if isinstance(hist2, pd.Series):
                        hist2 = hist2.to_frame().T
                    last = hist2.iloc[-1]
                    pc = last.get("Close", None) or last.get("close", None)
                    if pc is not None and not pd.isna(pc):
                        price = float(pc)
                        idx = last.name
                        ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                        used = "history(7d,1d)"
            except Exception:
                pass

        # fast_info fallback
        if price is None:
            try:
                fi = getattr(t, "fast_info", None)
                if fi:
                    if isinstance(fi, dict):
                        for k in ("lastPrice", "last_trade_price", "last_price", "last"):
                            if fi.get(k) is not None:
                                price = float(fi[k])
                                used = f"fast_info[{k}]"
                                break
                    else:
                        # sometimes fast_info is object-like
                        try:
                            lastp = fi.get("lastPrice") if hasattr(fi, "get") else None
                            if lastp:
                                price = float(lastp)
                                used = "fast_info[lastPrice]"
                        except Exception:
                            pass
            except Exception:
                pass

        # info fallback
        info = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}

        if price is None:
            try:
                cand = info.get("regularMarketPrice") or info.get("previousClose") or info.get("currentPrice") or info.get("price")
                if cand is not None and not pd.isna(cand):
                    price = float(cand)
                    used = "info"
            except Exception:
                pass

        # timestamp fallback
        if not ts:
            try:
                rmt = info.get("regularMarketTime") or info.get("regularMarketPreviousCloseTime")
                if isinstance(rmt, (int, float)):
                    ts = datetime.fromtimestamp(int(rmt), tz=timezone.utc).isoformat()
            except Exception:
                pass
        if not ts:
            ts = datetime.now(timezone.utc).isoformat()

        change = None
        change_percent = None
        previous_close = None
        marketCap = None
        pe_ratio = None
        currency = None

        try:
            change = info.get("regularMarketChange") or info.get("change")
        except Exception:
            pass
        try:
            change_percent = info.get("regularMarketChangePercent")
        except Exception:
            pass
        try:
            previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        except Exception:
            pass
        try:
            marketCap = info.get("marketCap")
        except Exception:
            pass
        try:
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        except Exception:
            pass
        try:
            currency = info.get("currency") or info.get("financialCurrency")
        except Exception:
            pass

        name = None
        try:
            for k in ("shortName", "longName", "name"):
                cand = info.get(k)
                if cand:
                    name = cand
                    break
        except Exception:
            pass

        realtime = {
            "symbol": ticker,
            "price": price,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "volume": volume,
            "previousClose": previous_close,
            "change": change,
            "changesPercentage": change_percent,
            "yearHigh": year_high,
            "yearLow": year_low,
            "marketCap": marketCap,
            "pe": pe_ratio,
            "currency": currency or "USD",
            "timestamp": ts,
            "_yf_used": used or "none"
        }

        if name:
            realtime["name"] = name
            realtime["companyName"] = name

        return {k: v for k, v in realtime.items() if v is not None}

    def _to_str_num(self, v, pick_key=None):
        try:
            if isinstance(v, (pd.Series, pd.DataFrame)):
                if isinstance(v, pd.DataFrame):
                    v = v.iloc[:, 0]
                if pick_key is not None and isinstance(v, pd.Series) and pick_key in v.index:
                    val = v[pick_key]
                else:
                    try:
                        val = v.dropna().iloc[0]
                    except Exception:
                        val = v.iloc[0] if len(v) > 0 else None
                v = val
            if isinstance(v, (list, tuple, np.ndarray)):
                v = next((x for x in v if x is not None and not (isinstance(x, float) and np.isnan(x))), None)
            if hasattr(v, "item"):
                try:
                    v = v.item()
                except Exception:
                    pass
            if v is None or pd.isna(v):
                return None, None
            if isinstance(v, (int, float, np.integer, np.floating)):
                s = ("{:.8f}".format(float(v))).rstrip("0").rstrip(".")
                return s, float(v)
            if isinstance(v, str):
                vs = v.replace(",", "").strip()
                try:
                    n = float(vs)
                    s = ("{:.8f}".format(n)).rstrip("0").rstrip(".")
                    return s, n
                except Exception:
                    return v, None
            try:
                n = float(v)
                s = ("{:.8f}".format(n)).rstrip("0").rstrip(".")
                return s, n
            except Exception:
                return str(v), None
        except Exception:
            try:
                return str(v), None
            except Exception:
                return None, None

    def _fmt_vol(self, v, pick_key=None):
        try:
            if isinstance(v, (pd.Series, pd.DataFrame)):
                if isinstance(v, pd.DataFrame):
                    v = v.iloc[:, 0]
                if pick_key is not None and isinstance(v, pd.Series) and pick_key in v.index:
                    v = v[pick_key]
                else:
                    try:
                        v = v.dropna().iloc[0]
                    except Exception:
                        v = v.iloc[0] if len(v) > 0 else None
            if isinstance(v, (list, tuple, np.ndarray)):
                v = next((x for x in v if x is not None and not (isinstance(x, float) and np.isnan(x))), None)
            if v is None or pd.isna(v):
                return None
            return int(float(str(v).replace(",", "")))
        except Exception:
            return None

    def _safe_date_val(self, val, fallback=None):
        try:
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if isinstance(val, pd.DataFrame):
                    val = val.iloc[:, 0]
                try:
                    val = val.dropna().iloc[0]
                except Exception:
                    try:
                        val = val.iloc[0]
                    except Exception:
                        val = fallback
            if isinstance(val, (list, tuple, np.ndarray)):
                val = next((x for x in val if x is not None and not (isinstance(x, float) and np.isnan(x))), fallback)
            if val is None:
                val = fallback
            if hasattr(val, "strftime"):
                return val.strftime("%b %d, %Y")
            parsed = pd.to_datetime(val, errors="coerce")
            if parsed is pd.NaT or parsed is None:
                return str(val) if val is not None else ""
            return parsed.strftime("%b %d, %Y")
        except Exception:
            try:
                return str(val)
            except Exception:
                return ""

    def _extract_ticker_subframe(self, df, requested_ticker):
        """Extract data for specific ticker from MultiIndex DataFrame (handles NSE/BSE fallback)."""
        try:  
            if not isinstance(df, pd.DataFrame):
                return df
            if isinstance(df.columns, pd.MultiIndex):
                cols = df.columns
                base = requested_ticker.split(".")[0] if "." in requested_ticker else requested_ticker
                candidates = [requested_ticker, base]
                for level in [1, 0]:
                    labels = [str(x) for x in cols.get_level_values(level)]
                    for cand in candidates:
                        if cand in labels:
                            try:
                                sub = df.xs(cand, axis=1, level=level, drop_level=True)
                                return sub
                            except Exception:
                                try:
                                    sub = df.loc[:, df.columns.get_level_values(level) == cand]
                                    if isinstance(sub.columns, pd.MultiIndex):
                                        sub.columns = sub.columns.droplevel(level)
                                    return sub
                                except Exception:
                                    continue
                if requested_ticker.endswith(".NS") or requested_ticker.endswith(".BO") or requested_ticker.endswith(".AE"):
                    base_ticker = requested_ticker.split(".")[0]
                    print(f"[DEBUG] Retrying subframe extraction for base ticker {base_ticker}")
                    try:
                        sub = df.xs(base_ticker, axis=1, level=1, drop_level=True)
                        return sub
                    except Exception:
                        pass
                try:
                    lvl1 = list(dict.fromkeys(df.columns.get_level_values(1)))
                    if lvl1:
                        sub = df.xs(lvl1[0], axis=1, level=1, drop_level=True)
                        return sub
                except Exception:
                    pass
            return df
        except Exception as e:
            print(f"[DEBUG] _extract_ticker_subframe failed for {requested_ticker}: {e}")
            return df

    def _yf_historical_try_methods(self, ticker: str, desired_period: str) -> dict:
        """
        Returns {"historical": [...]} with newest-first ordering.
        Each record: date, open, open_num, high, high_num, low, low_num, close, close_num, volume, ticker.
        """
        yf_period = self._YF_PERIOD_MAP.get(desired_period, "1mo")

        # Try yf.download first
        try:
            df = yf.download(ticker, period=yf_period, progress=False, threads=False, auto_adjust=False)
            if df is not None and not df.empty:
                df = self._extract_ticker_subframe(df, ticker)
                if df is not None and not df.empty:
                    if isinstance(df, pd.Series):
                        df = df.to_frame().T
                    df = df.reset_index()

                    print(f"[DEBUG] yf.download got {len(df)} rows for {ticker}, columns: {df.columns.tolist()}")

                    out = []
                    for _, row in df.iterrows():
                        date_val = row.get("Date", getattr(row, "name", None))
                        date_str = self._safe_date_val(date_val, fallback=row.name)
                        open_s, open_n = self._to_str_num(row.get("Open") if "Open" in row else row.get("open"))
                        high_s, high_n = self._to_str_num(row.get("High") if "High" in row else row.get("high"))
                        low_s, low_n = self._to_str_num(row.get("Low") if "Low" in row else row.get("low"))
                        close_s, close_n = self._to_str_num(row.get("Close") if "Close" in row else row.get("close"))
                        vol_i = self._fmt_vol(row.get("Volume") if "Volume" in row else row.get("volume"))

                        out.append({
                            "date": date_str,
                            "open": open_s,
                            "open_num": open_n,
                            "high": high_s,
                            "high_num": high_n,
                            "low": low_s,
                            "low_num": low_n,
                            "close": close_s,
                            "close_num": close_n,
                            "volume": vol_i,
                            "ticker": ticker
                        })

                    print(f"[DEBUG] yf.download returning {len(out)} formatted records")
                    return {"historical": out}
        except Exception as e:
            print(f"[DEBUG] yf.download failed for {ticker} period={yf_period}: {e}")

        # Try ticker.history as fallback
        try:
            t = yf.Ticker(ticker)
            end = datetime.now()
            days_map = {"1M": 30, "3M": 90, "6M": 180, "YTD": 365, "1Y": 365, "5Y": 365*5, "MAX": 365*20}
            days = days_map.get(desired_period, 30)
            start = end - timedelta(days=days)
            df2 = t.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval="1d", actions=False)
            if df2 is not None and not df2.empty:
                df2 = self._extract_ticker_subframe(df2, ticker)
                if isinstance(df2, pd.Series):
                    df2 = df2.to_frame().T
                df2 = df2.reset_index()
                out = []
                for _, row in df2.iterrows():
                    date_val = row.get("Date", getattr(row, "name", None))
                    date_str = self._safe_date_val(date_val, fallback=row.name)
                    open_s, open_n = self._to_str_num(row.get("Open") if "Open" in row else row.get("open"))
                    high_s, high_n = self._to_str_num(row.get("High") if "High" in row else row.get("high"))
                    low_s, low_n = self._to_str_num(row.get("Low") if "Low" in row else row.get("low"))
                    close_s, close_n = self._to_str_num(row.get("Close") if "Close" in row else row.get("close"))
                    vol_i = self._fmt_vol(row.get("Volume") if "Volume" in row else row.get("volume"))
                    out.append({
                        "date": date_str,
                        "open": open_s,
                        "open_num": open_n,
                        "high": high_s,
                        "high_num": high_n,
                        "low": low_s,
                        "low_num": low_n,
                        "close": close_s,
                        "close_num": close_n,
                        "volume": vol_i,
                        "ticker": ticker
                    })
                print(f"[DEBUG] ticker.history returning {len(out)} formatted records for {ticker}")
                return {"historical": out}
        except Exception as e:
            print(f"[DEBUG] Ticker.history failed for {ticker}: {e}")

        # Simple fallback
        try:
            print(f"[DEBUG] Trying simple 1y fallback history() for {ticker}")
            t = yf.Ticker(ticker)
            df3 = t.history(period="1y", interval="1d", actions=False)
            if df3 is not None and not df3.empty:
                df3 = df3.reset_index()
                out = []
                for _, row in df3.iterrows():
                    out.append({
                        "date": row["Date"].strftime("%b %d, %Y"),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"]),
                        "ticker": ticker
                    })
                print(f"[DEBUG] Simple fallback succeeded for {ticker} with {len(out)} records")
                return {"historical": out}
        except Exception as e:
            print(f"[DEBUG] Simple fallback also failed for {ticker}: {e}")

        print(f"[DEBUG] No valid historical data returned for {ticker}")
        return {"historical": []}

    def _try_yf_multi_periods(self, ticker: str, desired_period: str = "1M"):
        period_seq = []
        if desired_period and desired_period in self._YF_PERIOD_MAP:
            period_seq.append(desired_period)
        fallback_order = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]
        for p in fallback_order:
            if p not in period_seq:
                period_seq.append(p)

        cand_list = [ticker]
        if "." not in ticker:
            cand_list.extend([f"{ticker}.NS", f"{ticker}.BO", ticker])

        tried = []
        for c in cand_list:
            for p in period_seq:
                tried.append((c, p))
                try:
                    hist = self._yf_historical_try_methods(c, p)
                    lst = hist.get("historical") or []
                    if lst:
                        print(f"[DEBUG] yfinance success for candidate {c} period {p} => {len(lst)} rows")
                        return (p, lst, tried)
                except Exception as e:
                    print(f"[DEBUG] _try_yf_multi_periods: error for {c} {p}: {e}")
                    continue
        return (None, [], tried)

    def _fetch_historical_from_yf_and_format(self, ticker: str, desired_period: str = "1M"):
        p, lst, tried = self._try_yf_multi_periods(ticker, desired_period)
        if lst:
            for rec in lst:
                rec.setdefault("ticker", ticker)
                try:
                    dt = pd.to_datetime(rec.get("date"), errors="coerce")
                    if not pd.isna(dt):
                        rec["date"] = dt.strftime("%b %d, %Y")
                except Exception:
                    pass
                if ("open" not in rec or rec.get("open") is None) and rec.get("open_num") is not None:
                    rec["open"] = ("{:.8f}".format(rec["open_num"])).rstrip("0").rstrip(".")
                if ("high" not in rec or rec.get("high") is None) and rec.get("high_num") is not None:
                    rec["high"] = ("{:.8f}".format(rec["high_num"])).rstrip("0").rstrip(".")
                if ("low" not in rec or rec.get("low") is None) and rec.get("low_num") is not None:
                    rec["low"] = ("{:.8f}".format(rec["low_num"])).rstrip("0").rstrip(".")
                if ("close" not in rec or rec.get("close") is None) and rec.get("close_num") is not None:
                    rec["close"] = ("{:.8f}".format(rec["close_num"])).rstrip("0").rstrip(".")
                rec.setdefault("volume", rec.get("volume", None))
            return lst
        return None

    def _ensure_newest_first(self, lst):
        """Ensure list is sorted newest-first by date"""
        if not lst:
            return lst
        try:
            return sorted(lst, key=lambda r: pd.to_datetime(r.get("date")), reverse=False)
        except Exception:
            return lst

    def _normalize_historical_payload(self, historical_data):
        """Extract list of historical records from various formats"""
        if not historical_data:
            return None
        if isinstance(historical_data, list):
            return historical_data if historical_data else None
        if isinstance(historical_data, dict):
            for key in ("historical", "data", "rows", "results"):
                if key in historical_data and isinstance(historical_data[key], list) and historical_data[key]:
                    return historical_data[key]
            for v in historical_data.values():
                if isinstance(v, list) and v:
                    return v
        return None

    def _run(self, ticker_data: List[TickerSchema], explanation: str = None, period: str = "1M", strictly: bool = False):
        def process_ticker(ticker_info):
            ticker = getattr(ticker_info, "ticker", None)
            exchange_symbol = getattr(ticker_info, "exchange_symbol", None)
            result = {"realtime": None, "historical": None}

            # === REALTIME DATA ===
            realtime_response = None
            try:
                if exchange_symbol and ticker:
                    try:
                        url = f"https://financialmodelingprep.com/stable/quote/?symbol={ticker}&apikey={fm_api_key}"
                        currency_url = f'https://financialmodelingprep.com/stable/search-symbol?query={ticker}&apikey={fm_api_key}'
                        data_resp = requests.get(url, timeout=10)
                        search_resp = requests.get(currency_url, timeout=8)

                        if data_resp.ok:
                            fmp_json = data_resp.json()
                            if isinstance(fmp_json, list) and len(fmp_json) > 0 and isinstance(fmp_json[0], dict):
                                realtime_response = dict(fmp_json[0])
                                if search_resp.ok:
                                    currency_json = search_resp.json()
                                    if isinstance(currency_json, list) and len(currency_json) > 0:
                                        realtime_response["currency"] = currency_json[0].get("currency", "USD")
                                realtime_response.setdefault("currency", "USD")
                            else:
                                raise Exception("FMP returned invalid data")
                        else:
                            raise Exception(f"FMP HTTP {data_resp.status_code}")
                    except Exception as e_fmp:
                        print(f"[DEBUG] FMP realtime failed for {ticker}: {e_fmp}, falling back to yfinance")
                        cand = self._candidate_yf_tickers(ticker, exchange_symbol)
                        for c in cand:
                            try:
                                rt = self._yf_realtime(c)
                                if rt and rt.get("price") is not None:
                                    realtime_response = rt
                                    print(f"[DEBUG] yfinance realtime success for {c}")
                                    break
                            except Exception as e_yf:
                                print(f"[DEBUG] yfinance realtime failed for {c}: {e_yf}")
                                continue
                        if realtime_response is None:
                            realtime_response = {"error": "Failed to fetch realtime from FMP and yfinance."}
                else:
                    realtime_response = {"error": "Use web search tool for data not available from FMP."}
            except Exception as e:
                realtime_response = {"error": f"Failed to get realtime data: {str(e)}"}

            if isinstance(realtime_response, dict):
                if "symbol" not in realtime_response:
                    realtime_response["symbol"] = ticker
                if "timestamp" not in realtime_response or not realtime_response.get("timestamp"):
                    realtime_response["timestamp"] = datetime.now(timezone.utc).isoformat()
                if "companyName" not in realtime_response and "name" in realtime_response:
                    realtime_response["companyName"] = realtime_response.get("name")

            result["realtime"] = {k: v for k, v in (realtime_response or {}).items() if v is not None}

            # === HISTORICAL DATA ===
            try:
                periods = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]
                historical_data = None
                successful_period_index = None

                if exchange_symbol and ticker:
                    try:
                        if not strictly:
                            for i, p in enumerate(periods):
                                try:
                                    hist = mongodb.get_or_update_historical(ticker, p)
                                    normalized = self._normalize_historical_payload(hist)
                                    if normalized:
                                        historical_data = normalized
                                        successful_period_index = i
                                        print(f"[DEBUG] Got historical from MongoDB/FMP for {ticker} period {p}")
                                        break
                                except Exception as e_db:
                                    txt = str(e_db).lower()
                                    if "402" in txt or "payment required" in txt:
                                        print(f"[WARN] FMP payment required for {ticker}")
                                        historical_data = None
                                        break
                                    else:
                                        continue
                        else:
                            try:
                                hist = mongodb.get_or_update_historical(ticker, period)
                                historical_data = self._normalize_historical_payload(hist)
                            except Exception as e_db:
                                txt = str(e_db).lower()
                                if "402" in txt or "payment required" in txt:
                                    historical_data = None
                    except Exception as e_db_outer:
                        print(f"[ERROR] MongoDB outer exception for {ticker}: {e_db_outer}")
                        historical_data = None

                if historical_data:
                    try:
                        formatted_data = convert_fmp_to_json(historical_data, ticker)
                    except Exception as e_conv:
                        print(f"[WARN] convert_fmp_to_json failed: {e_conv}")
                        formatted_data = self._ensure_newest_first(historical_data)
                    formatted_data = self._ensure_newest_first(formatted_data)
                    result["historical"] = {
                        "source": "https://financialmodelingprep.com/",
                        "period": period if strictly else periods[successful_period_index:],
                        "data": formatted_data
                    }
                else:
                    # FMP failed, try yfinance
                    print(f"[DEBUG] FMP failed or empty, trying yfinance for {ticker}")
                    yf_success = False
                    candidates = self._candidate_yf_tickers(ticker, exchange_symbol)
                    all_tried = []
                    for cand in candidates:
                        chosen_period, yf_list, tried = self._try_yf_multi_periods(cand, desired_period=period if strictly else "1M")
                        all_tried.extend(tried if tried else [])
                        if yf_list:
                            for rec in yf_list:
                                rec.setdefault("ticker", ticker)
                                try:
                                    dt = pd.to_datetime(rec.get("date"), errors="coerce")
                                    if not pd.isna(dt):
                                        rec["date"] = dt.strftime("%b %d, %Y")
                                except Exception:
                                    pass
                                if ("open" not in rec or rec.get("open") is None) and rec.get("open_num") is not None:
                                    rec["open"] = ("{:.8f}".format(rec["open_num"])).rstrip("0").rstrip(".")
                                if ("high" not in rec or rec.get("high") is None) and rec.get("high_num") is not None:
                                    rec["high"] = ("{:.8f}".format(rec["high_num"])).rstrip("0").rstrip(".")
                                if ("low" not in rec or rec.get("low") is None) and rec.get("low_num") is not None:
                                    rec["low"] = ("{:.8f}".format(rec["low_num"])).rstrip("0").rstrip(".")
                                if ("close" not in rec or rec.get("close") is None) and rec.get("close_num") is not None:
                                    rec["close"] = ("{:.8f}".format(rec["close_num"])).rstrip("0").rstrip(".")
                                rec.setdefault("volume", rec.get("volume", None))

                            result["historical"] = {
                                "source": "yfinance",
                                "period": chosen_period or (period if strictly else "1M"),
                                "data": yf_list
                            }
                            yf_success = True
                            print(f"[DEBUG] yfinance historical success for candidate {cand} (period {chosen_period})")
                            break

                    if not yf_success:
                        print(f"[DEBUG] All yfinance candidates failed for {ticker}. Tried: {all_tried}")
                        result["historical"] = {
                            "error": "No data available after filtering",
                            "data": [],
                            "source": f"FMP+yfinance failed, tried candidates: {all_tried}"
                        }

            except Exception as e:
                print(f"[ERROR] Historical section failed for {ticker}: {e}")
                result["historical"] = {
                    "error": f"Stock history scrapping error: {e}",
                    "data": [],
                    "source": None
                }

            # --- FALLBACK REALTIME (CRITICAL) ---
            # If realtime earlier failed, synthesize a minimal realtime snapshot from the latest historical row
            try:
                hist_obj = result.get("historical") or {}
                hist_data = hist_obj.get("data") if isinstance(hist_obj, dict) else (hist_obj if isinstance(hist_obj, list) else [])
                latest_rec = None
                if isinstance(hist_data, list) and len(hist_data) > 0:
                    # pick last record as latest (we formatted dates as readable strings)
                    latest_rec = hist_data[-1]
                rt = result.get("realtime") or {}
                rt_error = isinstance(rt, dict) and ("error" in rt)
                if (not rt or rt_error or rt.get("price") is None) and latest_rec:
                    price_num = latest_rec.get("close_num") or None
                    if price_num is None:
                        try:
                            price_val = latest_rec.get("close")
                            price_num = float(str(price_val).replace(",", "")) if price_val is not None else None
                        except Exception:
                            price_num = None

                    if price_num is not None:
                        fallback_rt = {
                            "symbol": rt.get("symbol") or latest_rec.get("ticker") or ticker,
                            "price": float(price_num),
                            "previousClose": float(latest_rec.get("close_num")) if latest_rec.get("close_num") is not None else None,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "_yf_used": "historical_fallback"
                        }
                        if "companyName" in rt:
                            fallback_rt["companyName"] = rt["companyName"]
                        if "name" in rt:
                            fallback_rt.setdefault("companyName", rt["name"])
                        result["realtime"] = {k: v for k, v in fallback_rt.items() if v is not None}
                        print(f"[DEBUG] Populated fallback realtime for {ticker} from historical last record: {result['realtime']}")
                else:
                    if isinstance(rt, dict):
                        rt.setdefault("symbol", ticker)
                        rt.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                        result["realtime"] = {k: v for k, v in rt.items() if v is not None}
            except Exception as e:
                print(f"[DEBUG] Fallback realtime population failed for {ticker}: {e}")

            # === IS_ACTIVE CHECK ===
            try:
                data_list = []
                if isinstance(result.get("historical"), dict):
                    data_list = result["historical"].get("data", []) or []
                elif isinstance(result.get("historical"), list):
                    data_list = result["historical"]
                last_entry = data_list[0] if data_list else None
                if last_entry:
                    date_str = last_entry.get("date", "")
                    try:
                        if "-" in date_str:
                            last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        else:
                            last_date = datetime.strptime(date_str, "%b %d, %Y").date()
                        days_diff = (datetime.now().date() - last_date).days
                        result["historical"]["is_active"] = False if days_diff > 5 else True
                    except Exception:
                        result["historical"]["is_active"] = False
                else:
                    if isinstance(result.get("historical"), dict):
                        result["historical"]["is_active"] = False
            except Exception:
                if isinstance(result.get("historical"), dict):
                    result["historical"]["is_active"] = False
                else:
                    result["historical"] = {"error": "is_active check failed", "data": result.get("historical", {})}

            # === MESSAGE FIELD ===
            try:
                if (not isinstance(result.get('historical', {}), dict) or 'error' not in result['historical']) and (not isinstance(result.get('realtime', {}), dict) or 'error' not in result['realtime']):
                    result['message'] = "A graph has been generated and shown to the user so do not include this data in the response."
                else:
                    result['message'] = "Generate a graph based on this data which is visible to the user."
            except Exception:
                result['message'] = "Generate a graph based on this data which is visible to the user."

            return result

        # === MAIN EXECUTION WITH THREADPOOL ===
        all_results = []
        if not ticker_data:
            return all_results

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ticker_data)) as executor:
            future_to_ticker = {executor.submit(process_ticker, ticker_info): ticker_info for ticker_info in ticker_data}
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker_info = future_to_ticker[future]
                try:
                    res = future.result()
                    if not isinstance(res, dict):
                        res = {
                            "realtime": {
                                "symbol": getattr(ticker_info, "ticker", "unknown"),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            "historical": {"data": []},
                            "message": "Generate a graph based on this data which is visible to the user."
                        }
                    if "historical" not in res or not isinstance(res["historical"], dict):
                        res.setdefault("historical", {"data": []})
                    if "data" not in res["historical"]:
                        res["historical"].setdefault("data", [])
                    all_results.append(res)
                except Exception as e:
                    print(f"[ERROR] processing worker failed: {e}")
                    fallback = {
                        "realtime": {
                            "symbol": getattr(ticker_info, "ticker", "unknown"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        },
                        "historical": {"data": [], "error": str(e)},
                        "message": "Generate a graph based on this data which is visible to the user."
                    }
                    all_results.append(fallback)

        return all_results
    
class CombinedFinancialStatementTool(BaseTool):
    name: str = "get_financial_statements"
    description: str = """Always use this tool whenever user query involves any financial statement data (balance sheet, cash flow statement, or income statement) using various methods for companies in the U.S., India, and other regions and retrieves financial statements data.
    **Examples of when to call this tool:**
     - "Apple latest balance sheet 2024"
     - "Get Apple’s Q2 2025 income statement"
     - "Give me the balance sheet for Apple"
     - "Show Tesla's cash flow statement"
     - "Compare income statements of Google and Microsoft"
    """
    # description: str = """This tool retrieves financial statement data (balance sheet, cash flow statement, or income statement) using various methods for companies in the U.S., India, and other regions."""

    args_schema: Type[BaseModel] = CombinedFinancialStatementSchema

    def _run(self, symbol: str, exchangeShortName: str, statement_type: str, period: str = "annual", limit: int = 1, reporting_format: str = "standalone", explanation: str = None) -> str:

        external_data_dir = "external_data"
        os.makedirs(external_data_dir, exist_ok=True)
        timestamp = datetime.datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Fetch data based on the exchange
        # if exchangeShortName in ["NSE", "BSE"]:
        #     # return self._fetch_screener_data(symbol, statement_type, reporting_format, timestamp)
        #     return "Use web search tool for non USA data"
        if exchangeShortName and symbol:
            return self._fetch_us_data(symbol, statement_type, period, limit, timestamp)
        else:
            # return self._fetch_yahoo_data(symbol, statement_type, period, timestamp)
            return "Use web search tool for non USA data"

    # def _fetch_screener_data(self, symbol: str, statement_type: str, reporting_format: str, timestamp: str) -> str:
    #     """Fetches financial statements from Screener for NSE/BSE stocks."""
    #     try:
    #         symbol = symbol.split('.')[0]
    #         fetch_methods = {
    #             "balance_sheet": fetch_screener_balance_sheet,
    #             "cash_flow": fetch_screener_cashflow_results,
    #             "income_statement": fetch_screener_income_and_summary_results
    #         }
    #         fetch_function = fetch_methods[statement_type]

    #         if statement_type == "income_statement":
    #             results = fetch_function(symbol, reporting_format)
    #             currency, profit_loss_df, summary_df, url = results["currency"], results[
    #                 "profit_loss"], results["summary"], results["source"]

    #             data = {
    #                 "currency": currency,
    #                 "data": {
    #                     "profit_loss": profit_loss_df.to_dict(orient="records"),
    #                     "summary": summary_df.to_dict(orient="records") if not summary_df.empty else "No summary data available."
    #                 }
    #             }
    #             filename = f"{symbol}_{reporting_format}_incomeStatement_and_summary_{timestamp}.json"
    #             # formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- Profit & Loss:\n{profit_loss_df.to_markdown()}\n\n- Source: {url}"
    #             formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- Profit & Loss:\n{profit_loss_df.to_markdown()}"
    #             return self._pretty_return(data, filename, formatted_output, url)

    #         df, currency, url = fetch_function(symbol, reporting_format)
    #         data = {"currency": currency, "data": df.to_dict(orient="records")}
    #         filename = f"{symbol}_{reporting_format}_{statement_type}_{timestamp}.json"
    #         # formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- {statement_type}:\n{df.to_markdown()}\n\n- Source: {url}"
    #         formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- {statement_type}:\n{df.to_markdown()}"
    #         return self._pretty_return(data, filename, formatted_output, url)

    #     except Exception as e:
    #         return pretty_format(f"Error retrieving {statement_type} from Screener: {str(e)}")

    def _fetch_us_data(self, symbol: str, statement_type: str, period: str, limit: int, timestamp: str):
        """Fetches financial statements from FMP or Yahoo Finance for NYSE/NASDAQ stocks."""
        try:
            # FMP API Call
            fmp_endpoints = {
                "balance_sheet": "balance-sheet-statement",
                "cash_flow": "cash-flow-statement",
                "income_statement": "income-statement"
            }
            # url = f"https://financialmodelingprep.com/api/v3/{fmp_endpoints[statement_type]}/{symbol}?limit={limit}&apikey={fm_api_key}"
            # response = requests.get(url)
            # data = response.json()
            data = mongodb.fetch_financial_data(symbol, statement_type, limit=limit)

            if isinstance(data, list) and data:
                if period == 'quarterly':
                    data.append({"Note": "I don't have access to quarterly financial statement data."})
                return data
            else:
                # Fallback to Yahoo Finance
                # return self._fetch_yahoo_data(symbol, statement_type, period, timestamp)
                return data
        except Exception as e:
            error_msg = f"Error retrieving {statement_type} from Financial Modeling Prep: {str(e)}"
            return pretty_format(error_msg)

    # def _fetch_yahoo_data(self, symbol: str, statement_type: str, period: str, timestamp: str):
    #     """Fetches financial statements from Yahoo Finance as a backup."""
    #     try:
    #         yahoo_methods = {
    #             "balance_sheet": fetch_yahoo_finance_balance_sheet,
    #             "cash_flow": fetch_yahoo_finance_cash_flow_sheet,
    #             "income_statement": fetch_yahoo_finance_income_statement
    #         }
    #         fetch_function = yahoo_methods[statement_type]
    #         df, currency, url = fetch_function(symbol, period)

    #         data = {"currency": currency, "data": df.to_dict(orient="records")}
    #         filename = f"{symbol}_{statement_type}_{period}_{timestamp}.json"
    #         formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- {statement_type}:\n{df.to_markdown()}"
    #         return self._pretty_return(data, filename, formatted_output, url)

    #     except Exception as e:
    #         return pretty_format(f"Error retrieving {statement_type} from Yahoo Finance: {str(e)}")

    # def _pretty_return(self, data_dict: Dict, filename: str, formatted_output: str, url: str) -> str:
    #     """Handles JSON saving and returns a formatted response."""
    #     # asyncrunner.run_coroutine(mongodb.insert_in_db([{"filename": filename, "data": data_dict}]))
    #     return {"data": formatted_output, "source": url}


# class CurrencyRateTool(BaseTool):
#     name: str = "get_currency_exchange_rate"
#     description: str = """Use this tool to get the latest current currency exchange rates with USD as base."""

#     args_schema: Type[BaseModel] = CurrencyExchangeRateSchema

#     def _run(self, currencies: List[str] = ['INR', 'AED', 'EUR'], explanation: str = None):
#         try:
#             symbols_string = ",".join(currencies)
#             conn = http.client.HTTPSConnection("api.currencyfreaks.com")
#             payload = ''
#             headers = {}
#             url = f"/v2.0/rates/latest?apikey={currency_api_key}&symbols={symbols_string}"
#             conn.request("GET", url, payload, headers)
#             res = conn.getresponse()
#             data = res.read()
#             data = data.decode("utf-8")
#             return f"Current exchange rate: {data}"
#         except Exception as e:
#             error_msg = f"Can't get latest currency exchange rates due to error: {str(e)}"
#             return error_msg


class StockPriceChangeTool(BaseTool):
    name: str = "get_usa_based_company_stock_price_change"
    description: str = """Use this tool to get stock price change percentages over predefined periods (1D, 5D, 1M, etc.) for USA based companies only.
This tool provides information of companies registered in NYSE and NASDAQ only."""
    args_schema: Type[BaseModel] = CompanySymbolSchema

    def _run(self, symbol: str, explanation: str):
        try:
            # url = f"https://financialmodelingprep.com/api/v3/stock-price-change/{symbol}?apikey={fm_api_key}"
            # response = requests.get(url)

            # return pretty_format(response.json())
            response = mongodb.fetch_stock_price_change(symbol)
            return response
        except Exception as e:
            error_msg = f"Error in getting stock price changes: {str(e)}"
            return error_msg
        


class FinancialsDataSchema(BaseModel):
    """Input schema for the CompanyFinancialsTool."""
    symbols: List[str] = Field(..., description="A list of stock ticker symbols to fetch data for.")
    limit: int = Field(5, description="The number of historical annual periods to retrieve. Default is 5.")


class CompanyEssentialFinancialsTool(BaseTool):
    name: str = "get_essential_company_finance"
    description: str = """
    Use this tool to get comprehensive annual financial data for one or more stock symbols.
    It retrieves historical data for Revenue, Net Income, EPS, P/E Ratio, Market Cap,
    Net Profit Margin, and Cash & Investments from Financial Modeling Prep.
    """
    args_schema: Type[BaseModel] = FinancialsDataSchema

    def _run(self, symbols: List[str], limit: int = 5):
        print("===company agent===")
        all_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols)) as executor:
            future_to_symbol = {executor.submit(self._process_symbol, s, limit): s for s in symbols}
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    all_results.append(future.result())
                except Exception as e:
                    all_results.append({"symbol": symbol, "error": f"An unexpected error occurred: {str(e)}"})
        return all_results

    def _fetch_data(self, url: str):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as err:
            print(f"An error occurred: {err} for URL: {url}")
        return None

    def _process_symbol(self, symbol: str, limit: int):
        print(f"--Tool Call: Fetching financial data for {symbol}--")       

        base_url = "https://financialmodelingprep.com/stable"
        urls = {
            "income": f"{base_url}/income-statement?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}",
            "balance": f"{base_url}/balance-sheet-statement?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}",
            "metrics": f"{base_url}/key-metrics?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}",
            "ratios": f"{base_url}/ratios?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}"
        }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(self._fetch_data, url): key for key, url in urls.items()}
            data_map = {future_to_url[future]: future.result() for future in concurrent.futures.as_completed(future_to_url)}

        income_data, balance_data, metrics_data, ratios_data = data_map.get("income"), data_map.get("balance"), data_map.get("metrics"), data_map.get("ratios")

        if not all((income_data, balance_data, metrics_data)):
            return {"symbol": symbol, "error": "Failed to fetch complete financial data."}

        consolidated = {}
        for item in income_data:
            year = str(item.get("fiscalYear"))
            if year:
                consolidated[year] = {
                    "revenue": item.get("revenue"), 
                    "netIncome": item.get("netIncome"), 
                    "eps": item.get("eps")
                }
        
        for item in balance_data:
            year = str(item.get("fiscalYear"))
            if year in consolidated:
                consolidated[year]["cashAndInvestments"] = item.get("cashAndCashEquivalents", 0) + item.get("shortTermInvestments", 0)

        for item in metrics_data:
            year = str(item.get("fiscalYear"))
            if year in consolidated:
                consolidated[year].update({
                    "marketCap": item.get("marketCap"),
                })

        for item in ratios_data:
            year = str(item.get("fiscalYear"))
            if year in consolidated:
                consolidated[year].update({
                    "netProfitMargin": item.get("netProfitMargin"),
                    "priceToEarningsRatio": item.get("priceToEarningsRatio")                    
                })

        final_data = sorted([{"year": y, **d} for y, d in consolidated.items()], key=lambda x: x['year'], reverse=True)

        print("<data_returned_from_get_essential_company_finance>")
        print({"symbol": symbol, "financials": final_data})
        print("</data_returned_from_get_essential_company_finance>")
        
        return {"symbol": symbol, "financials": final_data}




# Pydantic models
class Metric(BaseModel):
    year: int = Field(description="The year of the financial metrics")
    gdp_growth_rate: Optional[float] = Field(description="Annual GDP growth rate in percentage")
    inflation_rate: Optional[float] = Field(description="Consumer Price Index inflation rate in percentage")
    debt_to_gdp_ratio: Optional[float] = Field(description="Debt as a percentage of GDP")
    trade_balance: Optional[float] = Field(description="Exports minus imports as a percentage of GDP")
    fdi_inflows: Optional[float] = Field(description="Foreign Direct Investment inflows as a percentage of GDP")

class CountryFinancial(BaseModel):
    country: str = Field(description="Name of the country")
    list_of_metrics: List[Metric] = Field(description="List of financial metrics for the country over different years")

class CountryFinancialInput(BaseModel):
    country: str = Field(description="Name of the country")

# Tavily web search function (as provided)
def tavily_web_search(query: str, num_results: int = 2):
    response = tavily_client.search(
        query=query,
        max_results=5,
        include_raw_content=False,
        search_depth="advanced",
        include_answer=True,
    )
    print("\n ============Here is list of answer from tavily ======== \n")
    print(response)
    print(" \n ============ End list of tavily answers ===========\n")
    
    concise_answer = response.get('answer')
    sources = [
        {
            'title': result.get('title', 'No Title'),
            'url': result.get('url'),
        }
        for result in response.get('results', [])
    ]
    formatted_results = {
        "concise answer": concise_answer,
        "sources": sources
    }
    print(f"formatted_results = {formatted_results}")
    return formatted_results

# CountryFinancialTool implementation
class CountryFinancialTool(BaseTool):
    name: str = "get_essential_country_economics"
    description: str = "Fetches GDP Growth Rate (Annual %), Inflation Rate (CPI, %), Debt-to-GDP Ratio (%), Trade Balance (% of GDP), and FDI Inflows (% of GDP) for a given country."
    args_schema: Type[BaseModel] = CountryFinancialInput

    def _run(self, country: str) -> CountryFinancial:

        print(" ====== Country Agent =======")
        current_year = datetime.now().year
        years = list(range(current_year -3 , current_year + 1))  # Last 4 years: 2021–2024
        metrics = [
            ("GDP growth rate", "gdp_growth_rate"),
            ("inflation rate", "inflation_rate"),
            ("debt-to-GDP ratio", "debt_to_gdp_ratio"),
            ("trade balance as a percentage of GDP", "trade_balance"),
            ("FDI inflows as a percentage of GDP", "fdi_inflows")
        ]
        
        # Generate questions
        questions = [
            f"what is the {metric[0]} for {country} for the year {year}?"
            for year in years
            for metric in metrics
        ]
        
        # Initialize the list of metrics for the country
        metric_list = []
        for year in years:
            metric_data = {
                "year": year,
                "gdp_growth_rate": None,
                "inflation_rate": None,
                "debt_to_gdp_ratio": None,
                "trade_balance": None,
                "fdi_inflows": None
            }
            
            # Query Tavily for each metric
            for metric_name, metric_key in metrics:
                query = f"what is the {metric_name} for {country} for the year {year}?"
                try:
                    result = tavily_web_search(query, num_results=2)
                    concise_answer = result.get("concise answer")
                    
                    # Extract numerical value from the answer
                    if concise_answer:
                        # Look for percentage values (e.g., "5.0%", "-1.2%")
                        numbers = re.findall(r"[-]?\d+\.?\d*%", concise_answer)
                        if numbers:
                            try:
                                value = float(numbers[0].strip("%"))
                                metric_data[metric_key] = value
                            except ValueError:
                                print(f"Failed to parse number for {metric_name}, {year}: {concise_answer}")
                        else:
                            print(f"No percentage value found for {metric_name}, {year}: {concise_answer}")
                    else:
                        print(f"No concise answer for {metric_name}, {year}")
                    time.sleep(1.2)  # Avoid rate limiting
                except Exception as e:
                    print(f"Error querying {metric_name} for {year}: {e}")
            
            metric_list.append(Metric(**metric_data))
        
        return CountryFinancial(country=country, list_of_metrics=metric_list)


# get_country_financial = CountryFinancialTool()
get_company_essential_financials = CompanyEssentialFinancialsTool()
search_company_info = SearchCompanyInfoTool()
# get_usa_based_company_profile = CompanyProfileTool()
get_stock_data = GetStockData()
get_financial_statements = CombinedFinancialStatementTool()
# get_currency_exchange_rates = CurrencyRateTool()
advanced_internet_search = AdvancedInternetSearchTool()
# get_market_capital_data = MarketCapTool()
# get_crypto_data_tool = GetCryptoDataTool()

tool_list = [
    search_company_info,
    get_stock_data,
    get_financial_statements,
    # get_currency_exchange_rates,
    advanced_internet_search,
    get_company_essential_financials,
    # get_market_capital_data
    # get_crypto_data_tool
]


if __name__ == "__main__":
    # Testing get_essential_company_finance tool
    get_company_essential_financials._run(symbols=["AMZN"])


## Old Code for Crypto:

# # Schema for input: Crypto Data
# class CryptoTickerSchema(BaseModel):
#     ticker: str  
#     from_date: Optional[str] = None
#     to_date: Optional[str] = None

# class CryptoDataSchema(BaseModel):
#     ticker_data: List[CryptoTickerSchema]
#     explanation: Optional[str] = None

# class GetCryptoDataTool(BaseTool):
#     name: str = "get_crypto_data_tool"
#     description: str = """Use this tool to get historical crypto data such as open, high, low, close, volume, and percent change.
# Provide cryptocurrency symbol (e.g., 'BTCUSD', 'ETHUSD') and optional date range (from_date, to_date)."""

#     args_schema: Type[BaseModel] = CryptoDataSchema

#     def _run(self, ticker_data: List[CryptoTickerSchema], explanation: Optional[str] = None):

#         fm_api_key = os.getenv("FM_API_KEY")
#         results = []

#         print(f"--- TOOL CALL - CRYPTO DATA ---")
#         print(f"ticker_data = {ticker_data}")

#         def fetch(symbol, from_date, to_date):
#             try:
#                 # Fallback to 30-day default if not provided
#                 if not to_date:
#                     to_date = datetime.date.today().isoformat()
#                 if not from_date:
#                     from_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

#                 data = get_crypto_data(symbol, fm_api_key, from_date, to_date)

#                 print(f"data = {data}")

#                 if not data:
#                     return {
#                         "symbol": symbol,
#                         "realtime": {
#                             "message": "Realtime data for cryptocurrencies is not currently supported."
#                         },
#                         "historical": {
#                             "data": [],
#                             "period": f"{from_date} to {to_date}",
#                             "source": "https://financialmodelingprep.com/developer/docs/cryptocurrency-api"
#                         },
#                         "message": "No historical data found."
#                     }

#                 return {
#                     "symbol": symbol,
#                     "realtime": {
#                         "message": "Realtime data for cryptocurrencies is not currently supported."
#                     },
#                     "historical": {
#                         "data": data,
#                         "period": f"{from_date} to {to_date}",
#                         "source": "https://financialmodelingprep.com/developer/docs/cryptocurrency-api"
#                     },
#                     "message": "Generate a graph based on this data which is visible to the user."
#                 }

#             except Exception as e:
#                 return {
#                     "symbol": symbol,
#                     "realtime": {"error": "Realtime data unavailable"},
#                     "historical": {"data": [], "error": str(e)},
#                     "message": f"Error retrieving data for {symbol}."
#                 }

#         with concurrent.futures.ThreadPoolExecutor(max_workers=len(ticker_data)) as executor:
#             futures = {
#                 executor.submit(fetch, item.ticker, item.from_date, item.to_date): item.ticker
#                 for item in ticker_data
#             }
#             for future in concurrent.futures.as_completed(futures):
#                 results.append(future.result())

#         return results