# uv run -m src.ai.tools.finance_data_tools
import asyncio
import aiohttp
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

from dotenv import load_dotenv
load_dotenv()


fm_api_key = os.getenv("FM_API_KEY")
currency_api_key = os.getenv("CURRENCY_FREAK_API_KEY")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


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


# class CompanyProfileTool(BaseTool):
#     name: str = "get_usa_based_company_profile"
#     description: str = """Use this tool to get company profile information through its ticker symbol.
# This tool provides information of companies registered."""
#     args_schema: Type[BaseModel] = CompanySymbolSchema

#     def _run(self, symbol: str, explanation: str):
#         try:
#             #url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={fm_api_key}"
#             #response = requests.get(url)
#             response=mongodb.get_or_fetch_company_profile(symbol)
#             # return pretty_format(response.json()) + "\n\n- Source: https://site.financialmodelingprep.com/"
#             #return {"data": response.json(), "source": "https://site.financialmodelingprep.com/"}
#             return response
#         except Exception as e:
#             error_msg = f"Error in getting company profile information: {str(e)}"
#             return error_msg


# class GetStockData(BaseTool):
    name: str = "get_stock_data"
    description: str = """Use this tool to get real-time stock quote data and historical stock prices of companies. The realtime stock data includes price, changes, market cap, PE ratio, and more.
    This tool generates a stock price chart which is only visible to the user.
"""
    args_schema: Type[BaseModel] = StockDataSchema

    def _run(self, ticker_data: List[TickerSchema], explanation: str = None, period: str = "1M", strictly: bool = False, toolCall = True):

        async def fetch(session, url):
            async with session.get(url) as response:
                return await response.json()

        async def get_stock_and_currency(ticker: str, fm_api_key: str):
            url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={fm_api_key}"
            currency_url = f'https://financialmodelingprep.com/stable/search-symbol?query={ticker}&apikey={fm_api_key}'

            async with aiohttp.ClientSession() as session:
                realtime_task = asyncio.create_task(fetch(session, url))
                currency_task = asyncio.create_task(fetch(session, currency_url))

                realtime_response, currency_data = await asyncio.gather(realtime_task, currency_task)

            return realtime_response, currency_data

        def process_ticker(ticker_info):
            ticker = ticker_info.ticker
            exchange_symbol = ticker_info.exchange_symbol
            result = {"realtime": None, "historical": None}

            # Fetch Real-Time Data
            # if toolCall :
            try:
                if exchange_symbol and ticker:
                    try:
                        realtime_response, currency_data = asyncio.run(get_stock_and_currency(ticker, fm_api_key))
                        realtime_currency = currency_data[0]["currency"] if currency_data else "USD"
                        realtime_response[0]["currency"] = realtime_currency
                        realtime_response = realtime_response[0]
                        realtime_response = {k: v for k, v in realtime_response.items() if v is not None}
                    except Exception as e:
                        try:
                            realtime_response = {"error":"No data found"} # fetch_yahoo_quote_data(ticker)
                                # if realtime_response.get("error"):
                                #     print("retrying ", retry_count)
                                # else:
                                #     break
                        except Exception as inner_e:
                            realtime_response = {"error": f"Error fetching realtime data : {str(inner_e)}"}
                        # except Exception as e:
                        #     realtime_response = {"error": f"Error fetching realtime data (USA backup): {str(e)}"}
                else:
                    realtime_response = {"error": "Use web search tool for data not available from FMP."}
                result["realtime"] = realtime_response
            except Exception as e:
                    result["realtime"] = {"error": f"Failed to get realtime data: {str(e)}"}
            # else :
            #     result["realtime"] = {"message": f"Data not needed for function call."}

            try:
                periods = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]   

                if exchange_symbol and ticker:
                    try:
                        historical_data = None
                        successful_period_index = None
                        if not strictly:
                            for i, p in enumerate(periods):
                                print(f"Trying period: {p}")
                                historical_data = mongodb.get_or_update_historical(ticker, p)
                                
                                if historical_data and len(historical_data) > 0:
                                    successful_period_index = i
                                    print(f"Data found for period: {p}")
                                    break
                                else:
                                    print(f"No data found for period: {p}")
                        else:
                            historical_data = mongodb.get_or_update_historical(ticker, period)

                        if 'historical' in historical_data and historical_data['historical']:
                            result["historical"] = {"source": "https://financialmodelingprep.com/"}
                            if strictly:
                                result["historical"]["period"] = period
                            else:
                                result["historical"]["period"]  = periods[successful_period_index:]

                            raw_data = historical_data['historical']
                            formatted_data = convert_fmp_to_json(raw_data, ticker)
                        else:
                            raise RuntimeError("No data available after filtering")

                        result["historical"]["data"] = formatted_data
                        # Check last 5 days activity
                        today = datetime.now().date()

                        # Get the last entry assuming it's the most recent date
                        data_list = []
                        if isinstance(historical_data, dict):
                            data_list = historical_data.get("historical", []) or historical_data.get("data", [])
                        elif isinstance(historical_data, list):
                            data_list = historical_data

                        # Take the last available record
                        last_entry = data_list[0] if data_list else None

                        if last_entry:
                            date_str = (last_entry.get("date") or "").strip().replace("\u00A0", " ")
                            try:
                                if "-" in date_str:
                                    last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                                else:
                                    last_date = datetime.strptime(date_str, "%b %d, %Y").date()

                                days_diff = (today - last_date).days
                                result["historical"]["is_active"] = False if days_diff > 5 else True
                            except Exception:
                                result["historical"]["is_active"] = False
                        else:
                            result["historical"]["is_active"] = False

                        

                    except Exception as e:
                        try:
                            historical_data = {"error":"No data found"} #scrape_yahoo_stock_history(ticker, period)
                            if isinstance(historical_data, dict) and historical_data.get("error"):
                                retry_count -= 1
                            else:
                                result["historical"] = {"data": historical_data, "source": f"https://finance.yahoo.com/quote/{ticker}/history", "period": periods}
                                
                            # Check last 5 days activity
                            today = datetime.now().date()
                            # Get the last entry assuming it's the most recent date
                            data_list = []
                            if isinstance(historical_data, dict):
                                data_list = historical_data.get("historical", []) or historical_data.get("data", [])
                            elif isinstance(historical_data, list):
                                data_list = historical_data

                            # Take the last available record
                            last_entry = data_list[0] if data_list else None

                            if last_entry:
                                date_str = (last_entry.get("date") or "").strip().replace("\u00A0", " ")
                                try:
                                    if "-" in date_str:
                                        last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                                    else:
                                        last_date = datetime.strptime(date_str, "%b %d, %Y").date()

                                    days_diff = (today - last_date).days
                                    result["historical"]["is_active"] = False if days_diff > 5 else True

                                except Exception:
                                    print
                                    result["historical"]["is_active"] = False
                            else:
                                print("last entry not found")
                                result["historical"]["is_active"] = False

                        except Exception as e:
                            historical_data = {"error": f"Error fetching historical data: {str(e)}"}                        
                else:
                    historical_data = {"error": "Use web search tool for data not available from FMP."}
            except Exception as e:
                error_msg = f"Stock history scrapping error: {e}"
                print(error_msg)
                result["historical"] = {"error": error_msg}
    
            if (not 'error' in result['historical']) and (not 'error' in result['realtime']):
                result['message'] = "A graph has been generated and shown to the user so do not include this data in the response."
            else:
                result['message'] = "Generate a graph based on this data which is visible to the user."
            return result
        
        all_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ticker_data)) as executor:
            future_to_ticker = {executor.submit(process_ticker, ticker_info): ticker_info for ticker_info in ticker_data}
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker_info = future_to_ticker[future]
                try:
                    result = future.result()
                    all_results.append(result)
                except Exception as e:
                    error_msg = f"Processing of {ticker_info.ticker} generated an exception: {str(e)}"
                    print(error_msg)

        return all_results

class GetStockData(BaseTool):
    name: str = "get_stock_data"
    description: str = """Use this tool to get real-time stock quote data and historical stock prices of companies. The realtime stock data includes price, changes, market cap, PE ratio, and more.
    This tool generates a stock price chart which is only visible to the user.
"""
    args_schema: Type[BaseModel] = StockDataSchema

    def _run(self, ticker_data: List[TickerSchema], explanation: str = None, period: str = "1M", strictly: bool = False, toolCall = True):

        async def fetch(session, url):
            async with session.get(url) as response:
                return await response.json()

        async def get_stock_and_currency(ticker: str, fm_api_key: str):
            url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={fm_api_key}"
            currency_url = f'https://financialmodelingprep.com/stable/search-symbol?query={ticker}&apikey={fm_api_key}'

            async with aiohttp.ClientSession() as session:
                realtime_task = asyncio.create_task(fetch(session, url))
                currency_task = asyncio.create_task(fetch(session, currency_url))

                realtime_response, currency_data = await asyncio.gather(realtime_task, currency_task)

            return realtime_response, currency_data

        def process_ticker(ticker_info):
            ticker = ticker_info.ticker
            exchange_symbol = ticker_info.exchange_symbol
            result = {"realtime": None, "historical": None}

            # Fetch Real-Time Data
            # if toolCall :
            try:
                if exchange_symbol and ticker:
                    try:
                        realtime_response, currency_data = asyncio.run(get_stock_and_currency(ticker, fm_api_key))
                        realtime_currency = currency_data[0]["currency"] if currency_data else "USD"
                        realtime_response[0]["currency"] = realtime_currency
                        realtime_response = realtime_response[0]
                        realtime_response = {k: v for k, v in realtime_response.items() if v is not None}
                    except Exception as e:
                        try:
                            realtime_response = {"error":"No data found"} # fetch_yahoo_quote_data(ticker)
                                # if realtime_response.get("error"):
                                #     print("retrying ", retry_count)
                                # else:
                                #     break
                        except Exception as inner_e:
                            realtime_response = {"error": f"Error fetching realtime data : {str(inner_e)}"}
                        # except Exception as e:
                        #     realtime_response = {"error": f"Error fetching realtime data (USA backup): {str(e)}"}
                else:
                    realtime_response = {"error": "Use web search tool for data not available from FMP."}
                result["realtime"] = realtime_response
            except Exception as e:
                    result["realtime"] = {"error": f"Failed to get realtime data: {str(e)}"}
            # else :
            #     result["realtime"] = {"message": f"Data not needed for function call."}

            try:
                periods = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]   

                if exchange_symbol and ticker:
                    try:
                        historical_data = None
                        successful_period_index = None
                        if not strictly:
                            for i, p in enumerate(periods):
                                print(f"Trying period: {p}")
                                historical_data = mongodb.get_or_update_historical(ticker, p)

                                # Normalize shape
                                if isinstance(historical_data, list):
                                    historical_data = {"historical": historical_data}
                                elif isinstance(historical_data, dict):
                                    if "data" in historical_data and "historical" not in historical_data:
                                        historical_data["historical"] = historical_data["data"]
                                print("------")
                                print(f"ticker = {ticker} | p = {p}")
                                print(f"historical_data - mongodb.get_or_update_historical = {historical_data}.")
                                print("------")
                                
                                if historical_data and len(historical_data) > 0:
                                    successful_period_index = i
                                    print(f"Data found for period: {p}")
                                    break
                                else:
                                    print(f"No data found for period: {p}")
                        else:
                            historical_data = mongodb.get_or_update_historical(ticker, period)

                        print(f"historical_data - mongodb.get_or_update_historical = {historical_data}.")
                        if 'historical' in historical_data and historical_data['historical']:
                            result["historical"] = {"source": "https://financialmodelingprep.com/"}
                            if strictly:
                                result["historical"]["period"] = period
                            else:
                                result["historical"]["period"]  = periods[successful_period_index:]

                            raw_data = historical_data['historical']
                            formatted_data = convert_fmp_to_json(raw_data, ticker)
                        else:
                            raise RuntimeError("No data available after filtering")

                        result["historical"]["data"] = formatted_data
                        # Check last 5 days activity
                        today = datetime.now().date()

                        # Get the last entry assuming it's the most recent date
                        data_list = []
                        if isinstance(historical_data, dict):
                            data_list = historical_data.get("historical", []) or historical_data.get("data", [])
                        elif isinstance(historical_data, list):
                            data_list = historical_data

                        # Take the last available record
                        last_entry = data_list[0] if data_list else None

                        if last_entry:
                            date_str = (last_entry.get("date") or "").strip().replace("\u00A0", " ")
                            try:
                                if "-" in date_str:
                                    last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                                else:
                                    last_date = datetime.strptime(date_str, "%b %d, %Y").date()

                                days_diff = (today - last_date).days
                                result["historical"]["is_active"] = False if days_diff > 5 else True
                            except Exception:
                                result["historical"]["is_active"] = False
                        else:
                            result["historical"]["is_active"] = False

                        

                    except Exception as e:
                        print(f"error: {e}")
                        try:
                            historical_data = {"error":"No data found"} # scrape_yahoo_stock_history(ticker, period)
                            if isinstance(historical_data, dict) and historical_data.get("error"):
                                result["historical"] = historical_data
                            else:
                                result["historical"] = {"data": historical_data, "source": f"https://finance.yahoo.com/quote/{ticker}/history", "period": periods}
                                
                            # Check last 5 days activity
                            today = datetime.now().date()
                            # Get the last entry assuming it's the most recent date
                            data_list = []
                            if isinstance(historical_data, dict):
                                data_list = historical_data.get("historical", []) or historical_data.get("data", [])
                            elif isinstance(historical_data, list):
                                data_list = historical_data

                            # Take the last available record
                            last_entry = data_list[0] if data_list else None

                            if last_entry:
                                date_str = (last_entry.get("date") or "").strip().replace("\u00A0", " ")
                                try:
                                    if "-" in date_str:
                                        last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                                    else:
                                        last_date = datetime.strptime(date_str, "%b %d, %Y").date()

                                    days_diff = (today - last_date).days
                                    if "historical" not in result:
                                         result["historical"] = {}
                                    result["historical"]["is_active"] = False if days_diff > 5 else True

                                except Exception:
                                    print
                                    if "historical" not in result:
                                         result["historical"] = {}
                                    result["historical"]["is_active"] = False
                            else:
                                print("last entry not found")
                                if "historical" not in result:
                                     result["historical"] = {}
                                result["historical"]["is_active"] = False

                        except Exception as e:
                            historical_data = {"error": f"Error fetching historical data: {str(e)}"}
                            result["historical"] = historical_data
                else:
                    historical_data = {"error": "Use web search tool for data not available from FMP."}
                    result["historical"] = historical_data
            except Exception as e:
                error_msg = f"Stock history scrapping error: {e}"
                print(error_msg)
                result["historical"] = {"error": error_msg}
    
            if (not 'error' in result['historical']) and (not 'error' in result['realtime']):
                result['message'] = "A graph has been generated and shown to the user so do not include this data in the response."
            else:
                result['message'] = "Generate a graph based on this data which is visible to the user."
            return result
        
        all_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ticker_data)) as executor:
            future_to_ticker = {executor.submit(process_ticker, ticker_info): ticker_info for ticker_info in ticker_data}
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker_info = future_to_ticker[future]
                try:
                    result = future.result()
                    all_results.append(result)
                except Exception as e:
                    error_msg = f"Processing of {ticker_info.ticker} generated an exception: {str(e)}"
                    print(error_msg)

        return all_results



# class CombinedFinancialStatementTool(BaseTool):
#     name: str = "get_financial_statements"
#     description: str = """Always use this tool whenever user query involves any financial statement data (balance sheet, cash flow statement, or income statement) using various methods for companies in the U.S., India, and other regions and retrieves financial statements data.
#     **Examples of when to call this tool:**
#      - "Apple latest balance sheet 2024"
#      - "Get Apple’s Q2 2025 income statement"
#      - "Give me the balance sheet for Apple"
#      - "Show Tesla's cash flow statement"
#      - "Compare income statements of Google and Microsoft"
#     """
#     # description: str = """This tool retrieves financial statement data (balance sheet, cash flow statement, or income statement) using various methods for companies in the U.S., India, and other regions."""

#     args_schema: Type[BaseModel] = CombinedFinancialStatementSchema

#     def _run(self, symbol: str, exchangeShortName: str, statement_type: str, period: str = "annual", limit: int = 1, reporting_format: str = "standalone", explanation: str = None) -> str:

#         external_data_dir = "external_data"
#         os.makedirs(external_data_dir, exist_ok=True)
#         timestamp = datetime.datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

#         # Fetch data based on the exchange
#         # if exchangeShortName in ["NSE", "BSE"]:
#         #     # return self._fetch_screener_data(symbol, statement_type, reporting_format, timestamp)
#         #     return "Use web search tool for non USA data"
#         if exchangeShortName and symbol:
#             return self._fetch_us_data(symbol, statement_type, period, limit, timestamp)
#         else:
#             # return self._fetch_yahoo_data(symbol, statement_type, period, timestamp)
#             return "Use web search tool for non USA data"

#     def _fetch_screener_data(self, symbol: str, statement_type: str, reporting_format: str, timestamp: str) -> str:
#         """Fetches financial statements from Screener for NSE/BSE stocks."""
#         try:
#             symbol = symbol.split('.')[0]
#             fetch_methods = {
#                 "balance_sheet": fetch_screener_balance_sheet,
#                 "cash_flow": fetch_screener_cashflow_results,
#                 "income_statement": fetch_screener_income_and_summary_results
#             }
#             fetch_function = fetch_methods[statement_type]

#             if statement_type == "income_statement":
#                 results = fetch_function(symbol, reporting_format)
#                 currency, profit_loss_df, summary_df, url = results["currency"], results[
#                     "profit_loss"], results["summary"], results["source"]

#                 data = {
#                     "currency": currency,
#                     "data": {
#                         "profit_loss": profit_loss_df.to_dict(orient="records"),
#                         "summary": summary_df.to_dict(orient="records") if not summary_df.empty else "No summary data available."
#                     }
#                 }
#                 filename = f"{symbol}_{reporting_format}_incomeStatement_and_summary_{timestamp}.json"
#                 # formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- Profit & Loss:\n{profit_loss_df.to_markdown()}\n\n- Source: {url}"
#                 formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- Profit & Loss:\n{profit_loss_df.to_markdown()}"
#                 return self._pretty_return(data, filename, formatted_output, url)

#             df, currency, url = fetch_function(symbol, reporting_format)
#             data = {"currency": currency, "data": df.to_dict(orient="records")}
#             filename = f"{symbol}_{reporting_format}_{statement_type}_{timestamp}.json"
#             # formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- {statement_type}:\n{df.to_markdown()}\n\n- Source: {url}"
#             formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- {statement_type}:\n{df.to_markdown()}"
#             return self._pretty_return(data, filename, formatted_output, url)

#         except Exception as e:
#             return pretty_format(f"Error retrieving {statement_type} from Screener: {str(e)}")

#     def _fetch_us_data(self, symbol: str, statement_type: str, period: str, limit: int, timestamp: str):
#         """Fetches financial statements from FMP or Yahoo Finance for NYSE/NASDAQ stocks."""
#         try:
#             # FMP API Call
#             fmp_endpoints = {
#                 "balance_sheet": "balance-sheet-statement",
#                 "cash_flow": "cash-flow-statement",
#                 "income_statement": "income-statement"
#             }
#             # url = f"https://financialmodelingprep.com/api/v3/{fmp_endpoints[statement_type]}/{symbol}?limit={limit}&apikey={fm_api_key}"
#             # response = requests.get(url)
#             # data = response.json()
#             data = mongodb.fetch_financial_data(symbol, statement_type, limit=limit)

#             if isinstance(data, list) and data:
#                 if period == 'quarterly':
#                     data.append({"Note": "I don't have access to quarterly financial statement data."})
#                 return data
#             else:
#                 # Fallback to Yahoo Finance
#                 # return self._fetch_yahoo_data(symbol, statement_type, period, timestamp)
#                 return data
#         except Exception as e:
#             error_msg = f"Error retrieving {statement_type} from Financial Modeling Prep: {str(e)}"
#             return pretty_format(error_msg)

#     def _fetch_yahoo_data(self, symbol: str, statement_type: str, period: str, timestamp: str):
#         """Fetches financial statements from Yahoo Finance as a backup."""
#         try:
#             yahoo_methods = {
#                 "balance_sheet": fetch_yahoo_finance_balance_sheet,
#                 "cash_flow": fetch_yahoo_finance_cash_flow_sheet,
#                 "income_statement": fetch_yahoo_finance_income_statement
#             }
#             fetch_function = yahoo_methods[statement_type]
#             df, currency, url = fetch_function(symbol, period)

#             data = {"currency": currency, "data": df.to_dict(orient="records")}
#             filename = f"{symbol}_{statement_type}_{period}_{timestamp}.json"
#             formatted_output = f"- Ticker: {symbol}\n- Currency: {currency}\n- {statement_type}:\n{df.to_markdown()}"
#             return self._pretty_return(data, filename, formatted_output, url)

#         except Exception as e:
#             return pretty_format(f"Error retrieving {statement_type} from Yahoo Finance: {str(e)}")

#     def _pretty_return(self, data_dict: Dict, filename: str, formatted_output: str, url: str) -> str:
#         """Handles JSON saving and returns a formatted response."""
#         # asyncrunner.run_coroutine(mongodb.insert_in_db([{"filename": filename, "data": data_dict}]))
#         return {"data": formatted_output, "source": url}


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


# class StockPriceChangeTool(BaseTool):
#     name: str = "get_usa_based_company_stock_price_change"
#     description: str = """Use this tool to get stock price change percentages over predefined periods (1D, 5D, 1M, etc.) for USA based companies only.
# This tool provides information of companies registered in NYSE and NASDAQ only."""
#     args_schema: Type[BaseModel] = CompanySymbolSchema

#     def _run(self, symbol: str, explanation: str):
#         try:
#             # url = f"https://financialmodelingprep.com/api/v3/stock-price-change/{symbol}?apikey={fm_api_key}"
#             # response = requests.get(url)

#             # return pretty_format(response.json())
#             response = mongodb.fetch_stock_price_change(symbol)
#             return response
#         except Exception as e:
#             error_msg = f"Error in getting stock price changes: {str(e)}"
#             return error_msg


# class CompanyEssentialFinancialsTool(BaseTool):
#     name: str = "get_essential_company_finance"
#     description: str = """
#     Use this tool to get comprehensive annual financial data for one or more stock symbols.
#     It retrieves historical data for Revenue, Net Income, EPS, P/E Ratio, Market Cap,
#     Net Profit Margin, and Cash & Investments from Financial Modeling Prep.
#     """
#     args_schema: Type[BaseModel] = FinancialsDataSchema

#     def _run(self, symbols: List[str], limit: int = 5):
#         print("===company agent===")
#         all_results = []
#         with concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols)) as executor:
#             future_to_symbol = {executor.submit(self._process_symbol, s, limit): s for s in symbols}
#             for future in concurrent.futures.as_completed(future_to_symbol):
#                 symbol = future_to_symbol[future]
#                 try:
#                     all_results.append(future.result())
#                 except Exception as e:
#                     all_results.append({"symbol": symbol, "error": f"An unexpected error occurred: {str(e)}"})
#         return all_results

#     def _fetch_data(self, url: str):
#         try:
#             response = requests.get(url)
#             response.raise_for_status()
#             return response.json()
#         except requests.exceptions.RequestException as err:
#             print(f"An error occurred: {err} for URL: {url}")
#         return None

#     def _process_symbol(self, symbol: str, limit: int):
#         print(f"--Tool Call: Fetching financial data for {symbol}--")       

#         base_url = "https://financialmodelingprep.com/stable"
#         urls = {
#             "income": f"{base_url}/income-statement?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}",
#             "balance": f"{base_url}/balance-sheet-statement?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}",
#             "metrics": f"{base_url}/key-metrics?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}",
#             "ratios": f"{base_url}/ratios?symbol={symbol}&period=annual&limit={limit}&apikey={fm_api_key}"
#         }
        
#         with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
#             future_to_url = {executor.submit(self._fetch_data, url): key for key, url in urls.items()}
#             data_map = {future_to_url[future]: future.result() for future in concurrent.futures.as_completed(future_to_url)}

#         income_data, balance_data, metrics_data, ratios_data = data_map.get("income"), data_map.get("balance"), data_map.get("metrics"), data_map.get("ratios")

#         if not all((income_data, balance_data, metrics_data)):
#             return {"symbol": symbol, "error": "Failed to fetch complete financial data."}

#         consolidated = {}
#         for item in income_data:
#             year = str(item.get("fiscalYear"))
#             if year:
#                 consolidated[year] = {
#                     "revenue": item.get("revenue"), 
#                     "netIncome": item.get("netIncome"), 
#                     "eps": item.get("eps")
#                 }
        
#         for item in balance_data:
#             year = str(item.get("fiscalYear"))
#             if year in consolidated:
#                 consolidated[year]["cashAndInvestments"] = item.get("cashAndCashEquivalents", 0) + item.get("shortTermInvestments", 0)

#         for item in metrics_data:
#             year = str(item.get("fiscalYear"))
#             if year in consolidated:
#                 consolidated[year].update({
#                     "marketCap": item.get("marketCap"),
#                 })

#         for item in ratios_data:
#             year = str(item.get("fiscalYear"))
#             if year in consolidated:
#                 consolidated[year].update({
#                     "netProfitMargin": item.get("netProfitMargin"),
#                     "priceToEarningsRatio": item.get("priceToEarningsRatio")                    
#                 })

#         final_data = sorted([{"year": y, **d} for y, d in consolidated.items()], key=lambda x: x['year'], reverse=True)

#         print("<data_returned_from_get_essential_company_finance>")
#         print({"symbol": symbol, "financials": final_data})
#         print("</data_returned_from_get_essential_company_finance>")
        
#         return {"symbol": symbol, "financials": final_data}




# Pydantic models
# class Metric(BaseModel):
#     year: int = Field(description="The year of the financial metrics")
#     gdp_growth_rate: Optional[float] = Field(description="Annual GDP growth rate in percentage")
#     inflation_rate: Optional[float] = Field(description="Consumer Price Index inflation rate in percentage")
#     debt_to_gdp_ratio: Optional[float] = Field(description="Debt as a percentage of GDP")
#     trade_balance: Optional[float] = Field(description="Exports minus imports as a percentage of GDP")
#     fdi_inflows: Optional[float] = Field(description="Foreign Direct Investment inflows as a percentage of GDP")

# class CountryFinancial(BaseModel):
#     country: str = Field(description="Name of the country")
#     list_of_metrics: List[Metric] = Field(description="List of financial metrics for the country over different years")

# class CountryFinancialInput(BaseModel):
#     country: str = Field(description="Name of the country")

# # Tavily web search function (as provided)
# def tavily_web_search(query: str, num_results: int = 2):
#     response = tavily_client.search(
#         query=query,
#         max_results=5,
#         include_raw_content=False,
#         search_depth="advanced",
#         include_answer=True,
#     )
#     print("\n ============Here is list of answer from tavily ======== \n")
#     print(response)
#     print(" \n ============ End list of tavily answers ===========\n")
    
#     concise_answer = response.get('answer')
#     sources = [
#         {
#             'title': result.get('title', 'No Title'),
#             'url': result.get('url'),
#         }
#         for result in response.get('results', [])
#     ]
#     formatted_results = {
#         "concise answer": concise_answer,
#         "sources": sources
#     }
#     print(f"formatted_results = {formatted_results}")
#     return formatted_results

# CountryFinancialTool implementation
# class CountryFinancialTool(BaseTool):
#     name: str = "get_essential_country_economics"
#     description: str = "Fetches GDP Growth Rate (Annual %), Inflation Rate (CPI, %), Debt-to-GDP Ratio (%), Trade Balance (% of GDP), and FDI Inflows (% of GDP) for a given country."
#     args_schema: Type[BaseModel] = CountryFinancialInput

#     def _run(self, country: str) -> CountryFinancial:

#         print(" ====== Country Agent =======")
#         current_year = datetime.now().year
#         years = list(range(current_year -3 , current_year + 1))  # Last 4 years: 2021–2024
#         metrics = [
#             ("GDP growth rate", "gdp_growth_rate"),
#             ("inflation rate", "inflation_rate"),
#             ("debt-to-GDP ratio", "debt_to_gdp_ratio"),
#             ("trade balance as a percentage of GDP", "trade_balance"),
#             ("FDI inflows as a percentage of GDP", "fdi_inflows")
#         ]
        
#         # Generate questions
#         questions = [
#             f"what is the {metric[0]} for {country} for the year {year}?"
#             for year in years
#             for metric in metrics
#         ]
        
#         # Initialize the list of metrics for the country
#         metric_list = []
#         for year in years:
#             metric_data = {
#                 "year": year,
#                 "gdp_growth_rate": None,
#                 "inflation_rate": None,
#                 "debt_to_gdp_ratio": None,
#                 "trade_balance": None,
#                 "fdi_inflows": None
#             }
            
#             # Query Tavily for each metric
#             for metric_name, metric_key in metrics:
#                 query = f"what is the {metric_name} for {country} for the year {year}?"
#                 try:
#                     result = tavily_web_search(query, num_results=2)
#                     concise_answer = result.get("concise answer")
                    
#                     # Extract numerical value from the answer
#                     if concise_answer:
#                         # Look for percentage values (e.g., "5.0%", "-1.2%")
#                         numbers = re.findall(r"[-]?\d+\.?\d*%", concise_answer)
#                         if numbers:
#                             try:
#                                 value = float(numbers[0].strip("%"))
#                                 metric_data[metric_key] = value
#                             except ValueError:
#                                 print(f"Failed to parse number for {metric_name}, {year}: {concise_answer}")
#                         else:
#                             print(f"No percentage value found for {metric_name}, {year}: {concise_answer}")
#                     else:
#                         print(f"No concise answer for {metric_name}, {year}")
#                     time.sleep(1.2)  # Avoid rate limiting
#                 except Exception as e:
#                     print(f"Error querying {metric_name} for {year}: {e}")
            
#             metric_list.append(Metric(**metric_data))
        
#         return CountryFinancial(country=country, list_of_metrics=metric_list)


# class CountryFinancialTool(BaseTool):
#     name: str = "get_essential_country_economics"
#     description: str = (
#         "Fetches GDP Growth Rate (Annual %), Inflation Rate (CPI, %), Debt-to-GDP Ratio (%), "
#         "Trade Balance (% of GDP), and FDI Inflows (% of GDP) for a given country and year range."
#     )
#     args_schema: Type[BaseModel] = CountryFinancialInput

#     # def __init__(self):
#     #     self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
#     #     if not self.perplexity_api_key:
#     #         raise RuntimeError("PERPLEXITY_API_KEY not set in environment variables.")

#     def determine_year_range(self, start_year: int, end_year: int, mentioned_years: Optional[List[int]] = None):
#         current_year = datetime.now().year
#         if start_year is not None and end_year is not None:
#             y0, y1 = start_year, end_year
#             if y1 - y0 + 1 < 5:
#                 expand = 5 - (y1 - y0 + 1)
#                 y0 = y0 - expand // 2
#                 y1 = y1 + expand // 2 + (expand % 2)
#             return y0, y1
#         if mentioned_years:
#             if len(mentioned_years) == 1:
#                 y = mentioned_years[0]
#                 return y - 2, y + 2
#             else:
#                 y0, y1 = min(mentioned_years), max(mentioned_years)
#                 if y1 - y0 + 1 < 5:
#                     expand = 5 - (y1 - y0 + 1)
#                     y0 = y0 - expand // 2
#                     y1 = y1 + expand // 2 + (expand % 2)
#                 return y0, y1
#         return current_year - 4, current_year

#     def build_perplexity_prompt(self, country: str, start_year: int, end_year: int) -> str:
#         return (
#             f"Fetch the following financial metrics for {country} for each year from {start_year} to {end_year} (inclusive):\n"
#             "- GDP Growth Rate (Annual %)\n"
#             "- Inflation Rate (Consumer Price Index, %)\n"
#             "- Debt-to-GDP Ratio (%)\n"
#             "- Trade Balance (% of GDP)\n"
#             "- Foreign Direct Investment Inflows (% of GDP)\n\n"
#             "For each year, provide the metrics as numeric values (percentages as numbers). "
#             "If data is not available for a metric/year, set it as null. "
#             "Return the data strictly in the JSON format matching this schema:\n"
#             "{"
#             '"country": "string",'
#             '"list_of_metrics": ['
#             '  {'
#             '    "year": int,'
#             '    "gdp_growth_rate": float | null,'
#             '    "inflation_rate": float | null,'
#             '    "debt_to_gdp_ratio": float | null,'
#             '    "trade_balance": float | null,'
#             '    "fdi_inflows": float | null'
#             '  }, ...'
#             ']'
#             "}\n"
#         )

#     def _run(self, country: str, start_year: int = None, end_year: int = None, mentioned_years: Optional[List[int]] = None):
#         print(f"\n===Country financial tool call 1 {country}===")
#         sy, ey = self.determine_year_range(start_year, end_year, mentioned_years)
#         print("\n===Country financial tool call 3===")
#         prompt = self.build_perplexity_prompt(country, sy, ey)
#         print("\n===Country financial tool call 3===")
#         print(f"\n===Prompt to Perplexity: {prompt}===\n")
#         url = "https://api.perplexity.ai/chat/completions"
#         headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}"}
#         payload = {
#             "model": "sonar",
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": prompt
#                 }
#             ],
#             "response_format": {
#                 "type": "json_schema",
#                 "json_schema": {
#                     "schema": CountryFinancial.model_json_schema()
#                 }
#             }
#         }

#         response = requests.post(url, headers=headers, json=payload)
#         data = response.json()
#         print(f"\n===Raw Perplexity response:{data}===\n")
#         try:
#             content = data["choices"][0]["message"]["content"]
#             print(f"\n===LLM returned content: {content}===\n")
#             country_financials = CountryFinancial.model_validate_json(content)
#             return country_financials
#         except Exception as e:
#             print("[ERROR] Failed to parse/validate Perplexity output:", e)
#             return e
        
# class GetHistoricalStockData(BaseTool):
#     """
#     BaseTool wrapper for FinancialModelingPrep's /historical-price-eod/full endpoint.

#     Usage:
#         tool = GetHistoricalStockData()
#         result = tool._run("AAPL", from_date="2024-01-01", to_date="2024-06-30")
#     """
#     name: str = "get_historical_data"
#     description: str = (
#         "Fetches end-of-day historical price data for a given stock ticker and optional date range "
#         "(YYYY-MM-DD). Returns the JSON response from FinancialModelingPrep."
#     )
#     args_schema: Type[BaseModel] = GetHistoricalStockData

#     def _run(self, ticker: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict[str, Any]:
#         """Synchronous execution (requests)."""
#         print(f"TOOL: Fetching EOD historical stock data for {ticker} (sync)...")

#         # # Validate API key presence in module/global scope
#         # global fm_api_key
#         # if not globals().get("fm_api_key") or fm_api_key == "your_fmp_api_key_here":
#         #     return {"error": "FMP API key is not configured."}

#         url = "https://financialmodelingprep.com/stable/historical-price-eod/full"
#         params = {"symbol": ticker, "apikey": fm_api_key}
#         if from_date:
#             params["from"] = from_date
#         if to_date:
#             params["to"] = to_date

#         try:
#             resp = requests.get(url, params=params, timeout=30)
#             resp.raise_for_status()
#             data = resp.json()
#             # Optional: small sleep to be nice to API (mirror your previous pattern)
#             time.sleep(0.2)
#             return data
#         except requests.HTTPError as he:
#             print(f"HTTP error: {he}")
#             return {"error": "HTTP error", "detail": str(he), "status_code": getattr(he.response, "status_code", None)}
#         except Exception as e:
#             print(f"Unexpected error: {e}")
#             return {"error": "Unexpected error", "detail": str(e)}


# get_essential_country_economics = CountryFinancialTool()
# get_company_essential_financials = CompanyEssentialFinancialsTool()
search_company_info = SearchCompanyInfoTool()
# get_usa_based_company_profile = CompanyProfileTool()
get_stock_data = GetStockData()
# get_financial_statements = CombinedFinancialStatementTool()
# get_currency_exchange_rates = CurrencyRateTool()
# advanced_internet_search = AdvancedInternetSearchToolPerplexity()
# get_market_capital_data = MarketCapTool()
# get_crypto_data_tool = GetCryptoDataTool()
# get_historical_data = GetHistoricalStockData()

tool_list = [
    search_company_info,
    get_stock_data,
    # get_financial_statements,
    # get_currency_exchange_rates,
    # advanced_internet_search,
    # get_company_essential_financials,
    # get_essential_country_economics,
    # get_market_capital_data
    # get_crypto_data_tool
    # get_historical_data
]


# if __name__ == "__main__":
#     # Testing get_essential_company_finance tool
#     get_company_essential_financials._run(symbols=["AMZN"])

if __name__ == "__main__":
    test_ticker_data = [
        TickerSchema(
            ticker="RELIANCE.BO",
            exchange_symbol="BSE"
        )
    ]
    explanation = "Fetch stock data for Reliance Industries listed on the Bombay Stock Exchange."
    
    get_stock_data = GetStockData()
    result = get_stock_data._run(ticker_data=test_ticker_data, explanation=explanation)
    print(result)


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