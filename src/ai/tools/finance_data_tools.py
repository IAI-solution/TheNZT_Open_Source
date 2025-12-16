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
        """Fetch realtime data from yfinance, with open/high/low/volume/pe/marketCap/yearHigh/yearLow."""
        t = yf.Ticker(ticker)
        price = None
        ts = None
        used = None

        # Try intraday history for freshest close
        try:
            for p, interval in (("1d", "1m"), ("5d", "5m")):
                try:
                    hist = t.history(period=p, interval=interval, actions=False)
                    if hist is not None and not hist.empty:
                        last = hist.iloc[-1]
                        close_candidate = last.get("Close") or last.get("close")
                        if close_candidate is not None and not pd.isna(close_candidate):
                            price = float(close_candidate)
                            idx = last.name
                            ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                            used = f"history({p},{interval})"
                            break
                except Exception:
                    pass
        except Exception:
            pass

        # fallback to recent daily
        if price is None:
            try:
                hist2 = t.history(period="7d", interval="1d", actions=False)
                if hist2 is not None and not hist2.empty:
                    last = hist2.iloc[-1]
                    pc = last.get("Close") or last.get("close")
                    if pc is not None and not pd.isna(pc):
                        price = float(pc)
                        idx = last.name
                        ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                        used = "history(7d,1d)"
            except Exception:
                pass

        # get info (fast_info / info)
        info = {}
        try:
            info = t.fast_info or (t.info or {})
        except Exception:
            try:
                info = t.info or {}
            except Exception:
                info = {}

        # info-based fallbacks
        def _g(*keys):
            for k in keys:
                v = info.get(k)
                if v is not None:
                    return v
            return None

        if price is None:
            cand = _g("regularMarketPrice", "currentPrice", "previousClose", "lastPrice", "price")
            try:
                if cand is not None and not pd.isna(cand):
                    price = float(cand)
                    used = "info"
            except Exception:
                pass

        if not ts:
            try:
                rmt = _g("regularMarketTime", "regularMarketPreviousCloseTime")
                if isinstance(rmt, (int, float)):
                    ts = datetime.fromtimestamp(int(rmt), tz=timezone.utc).isoformat()
            except Exception:
                pass
        if not ts:
            ts = datetime.now(timezone.utc).isoformat()

        open_price = _g("open", "regularMarketOpen", "previousOpen")
        high_price = _g("dayHigh", "regularMarketDayHigh", "high")
        low_price = _g("dayLow", "regularMarketDayLow", "low")
        volume = _g("volume", "regularMarketVolume")
        year_high = _g("fiftyTwoWeekHigh", "52WeekHigh", "yearHigh")
        year_low = _g("fiftyTwoWeekLow", "52WeekLow", "yearLow")
        marketCap = _g("marketCap")
        pe_ratio = _g("trailingPE", "forwardPE")
        currency = _g("currency", "financialCurrency") or "USD"

        # backfill open/high/low/volume from latest daily row if missing
        try:
            need = any(x is None for x in (open_price, high_price, low_price, volume))
            if need:
                df_daily = t.history(period="7d", interval="1d", actions=False)
                if df_daily is not None and not df_daily.empty:
                    last = df_daily.iloc[-1]
                    open_price = open_price or (last.get("Open") if "Open" in last.index else last.get("open"))
                    high_price = high_price or (last.get("High") if "High" in last.index else last.get("high"))
                    low_price = low_price or (last.get("Low") if "Low" in last.index else last.get("low"))
                    volume = volume or (last.get("Volume") if "Volume" in last.index else last.get("volume"))
        except Exception:
            pass

        def _to_float(v):
            try:
                if v is None or pd.isna(v):
                    return None
                return float(v)
            except Exception:
                try:
                    return float(str(v).replace(",", ""))
                except Exception:
                    return None

        realtime = {
            "symbol": ticker,
            "price": _to_float(price),
            "open": _to_float(open_price),
            "high": _to_float(high_price),
            "low": _to_float(low_price),
            "volume": int(volume) if (volume is not None and not pd.isna(volume)) else None,
            "previousClose": _to_float(_g("previousClose", "regularMarketPreviousClose")),
            "change": _to_float(_g("regularMarketChange", "change")),
            "changesPercentage": _to_float(_g("regularMarketChangePercent")),
            "yearHigh": _to_float(year_high),
            "yearLow": _to_float(year_low),
            "marketCap": _to_float(marketCap),
            "pe": _to_float(pe_ratio),
            "currency": currency,
            "timestamp": ts,
            "_yf_used": used or "none"
        }

        name = None
        try:
            for k in ("shortName", "longName", "name"):
                if k in info and info.get(k):
                    name = info.get(k)
                    break
        except Exception:
            pass

        if name:
            realtime["name"] = name
            realtime["companyName"] = name

        # remove None values
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

            # --- REALTIME: always use yfinance ---
            try:
                candidates = self._candidate_yf_tickers(ticker, exchange_symbol)
                realtime_response = None
                for c in candidates:
                    try:
                        rt = self._yf_realtime(c)
                        if rt and rt.get("price") is not None:
                            realtime_response = rt
                            break
                    except Exception:
                        continue
                if realtime_response is None:
                    realtime_response = {"error": "yfinance realtime failed for all candidates"}
            except Exception as e:
                realtime_response = {"error": f"Realtime fetch failed: {e}"}

            # ensure some fields
            if isinstance(realtime_response, dict):
                realtime_response.setdefault("symbol", ticker)
                realtime_response.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                if "companyName" not in realtime_response and "name" in realtime_response:
                    realtime_response["companyName"] = realtime_response.get("name")

            result["realtime"] = {k: v for k, v in (realtime_response or {}).items() if v is not None}

            # --- HISTORICAL: always use yfinance ---
            try:
                yf_success = False
                all_candidates = self._candidate_yf_tickers(ticker, exchange_symbol)
                chosen_period = None
                yf_list = None
                for cand in all_candidates:
                    p, lst, tried = self._try_yf_multi_periods(cand, desired_period=period if strictly else "1M")
                    if lst:
                        chosen_period = p
                        yf_list = lst
                        break

                if yf_list:
                    # normalize formatting to match frontend expectations
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

                if not yf_success:
                    result["historical"] = {
                        "error": "No historical data available from yfinance",
                        "data": [],
                        "source": "yfinance"
                    }

            except Exception as e:
                result["historical"] = {"error": f"Historical yfinance fetch failed: {e}", "data": [], "source": "yfinance"}

            # --- FALLBACK REALTIME FROM HIST if realtime missing ---
            try:
                hist_obj = result.get("historical") or {}
                hist_data = hist_obj.get("data") if isinstance(hist_obj, dict) else (hist_obj if isinstance(hist_obj, list) else [])
                latest_rec = None
                if isinstance(hist_data, list) and len(hist_data) > 0:
                    latest_rec = hist_data[-1]  # last record
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
                        result["realtime"] = {k: v for k, v in fallback_rt.items() if v is not None}
            except Exception:
                pass

            # is_active check (same logic as before)
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

            # === NORMALIZE & ADD FRONTEND-FRIENDLY KEYS ===
            try:
                # Helper enforcers
                def _to_number(v):
                    try:
                        if v is None:
                            return None
                        if isinstance(v, str):
                            v = v.replace(",", "").strip()
                        if isinstance(v, (int, float, np.integer, np.floating)):
                            return float(v)
                        return float(v)
                    except Exception:
                        return None

                def _to_int(v):
                    try:
                        n = _to_number(v)
                        return int(n) if n is not None else None
                    except Exception:
                        return None

                # Ensure realtime exists and is dict
                rt = result.get("realtime") or {}
                if isinstance(rt, dict):
                    # gather variants from possible keys
                    rt_price = rt.get("price") or rt.get("close") or rt.get("last")
                    rt_open = rt.get("open") or rt.get("open_num")
                    rt_high = rt.get("high") or rt.get("high_num") or rt.get("dayHigh")
                    rt_low = rt.get("low") or rt.get("low_num") or rt.get("dayLow")
                    rt_prev = rt.get("previousClose") or rt.get("prevClose") or rt.get("previous_close")
                    rt_vol = rt.get("volume") or rt.get("vol")
                    rt_pe = rt.get("pe") or rt.get("peRatio") or rt.get("trailingPE") or rt.get("forwardPE")
                    rt_mcap = rt.get("marketCap") or rt.get("market_cap") or rt.get("marketCapitalization")
                    rt_yearHigh = rt.get("yearHigh") or rt.get("fiftyTwoWeekHigh") or rt.get("52WeekHigh")
                    rt_yearLow = rt.get("yearLow") or rt.get("fiftyTwoWeekLow") or rt.get("52WeekLow")

                    # canonical numeric fields
                    rt["price"] = _to_number(rt_price)
                    rt["open"] = _to_number(rt_open)
                    rt["high"] = _to_number(rt_high)
                    rt["low"] = _to_number(rt_low)
                    rt["previousClose"] = _to_number(rt_prev)
                    rt["volume"] = _to_int(rt_vol)
                    rt["marketCap"] = _to_number(rt_mcap)
                    rt["yearHigh"] = _to_number(rt_yearHigh)
                    rt["yearLow"] = _to_number(rt_yearLow)
                    rt["pe"] = _to_number(rt_pe)

                    # add common aliases the frontend may look for
                    rt.setdefault("peRatio", rt.get("pe"))
                    rt.setdefault("pe_ratio", rt.get("pe"))
                    rt.setdefault("PE", rt.get("pe"))
                    # keep name/companyName if present
                    if "companyName" in rt and "name" not in rt:
                        rt["name"] = rt["companyName"]
                    if "name" in rt and "companyName" not in rt:
                        rt["companyName"] = rt["name"]

                    # make sure symbol/timestamp exist
                    rt.setdefault("symbol", ticker)
                    rt.setdefault("timestamp", rt.get("timestamp") or datetime.now(timezone.utc).isoformat())

                    # write back normalized realtime
                    result["realtime"] = {k: v for k, v in rt.items() if v is not None}

                # Build a small 'latest' summary object (frontends often read this)
                latest_summary = {
                    "symbol": result.get("realtime", {}).get("symbol") or ticker,
                    "open": result.get("realtime", {}).get("open"),
                    "high": result.get("realtime", {}).get("high"),
                    "low": result.get("realtime", {}).get("low"),
                    "close": result.get("realtime", {}).get("price"),
                    "previousClose": result.get("realtime", {}).get("previousClose"),
                    "volume": result.get("realtime", {}).get("volume"),
                    "peRatio": result.get("realtime", {}).get("pe") or result.get("realtime", {}).get("peRatio"),
                    "marketCap": result.get("realtime", {}).get("marketCap"),
                    "timestamp": result.get("realtime", {}).get("timestamp") or datetime.now(timezone.utc).isoformat()
                }

                # attach summary in common places the frontend may inspect
                result["summary"] = latest_summary
                if isinstance(result.get("historical"), dict):
                    # Ensure historical data is normalized and each record has numeric *_num fields expected by frontend.
                    hist_data = result["historical"].get("data", []) or []
                    for rec in hist_data:
                        try:
                            # coerce string numeric fields into separate numeric fields if not present
                            if ("open_num" not in rec or rec.get("open_num") is None) and rec.get("open") is not None:
                                try:
                                    rec["open_num"] = _to_number(rec.get("open"))
                                except Exception:
                                    pass
                            if ("high_num" not in rec or rec.get("high_num") is None) and rec.get("high") is not None:
                                try:
                                    rec["high_num"] = _to_number(rec.get("high"))
                                except Exception:
                                    pass
                            if ("low_num" not in rec or rec.get("low_num") is None) and rec.get("low") is not None:
                                try:
                                    rec["low_num"] = _to_number(rec.get("low"))
                                except Exception:
                                    pass
                            if ("close_num" not in rec or rec.get("close_num") is None) and rec.get("close") is not None:
                                try:
                                    rec["close_num"] = _to_number(rec.get("close"))
                                except Exception:
                                    pass
                            if "volume" in rec and not isinstance(rec.get("volume"), (int, float)):
                                try:
                                    rec["volume"] = _to_int(rec.get("volume"))
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    # attach the latest summary under historical.latest for UIs that read there
                    if hist_data:
                        # choose last element as latest (keeps your present semantics)
                        result["historical"].setdefault("latest", {
                            "date": hist_data[-1].get("date"),
                            "open": hist_data[-1].get("open_num") or _to_number(hist_data[-1].get("open")),
                            "high": hist_data[-1].get("high_num") or _to_number(hist_data[-1].get("high")),
                            "low": hist_data[-1].get("low_num") or _to_number(hist_data[-1].get("low")),
                            "close": hist_data[-1].get("close_num") or _to_number(hist_data[-1].get("close")),
                            "volume": hist_data[-1].get("volume")
                        })
                    result["historical"]["data"] = hist_data

                # ensure message remains set
                try:
                    if (not isinstance(result.get('historical', {}), dict) or 'error' not in result['historical']) and (not isinstance(result.get('realtime', {}), dict) or 'error' not in result['realtime']):
                        result['message'] = "A graph has been generated and shown to the user so do not include this data in the response."
                    else:
                        result['message'] = "Generate a graph based on this data which is visible to the user."
                except Exception:
                    result['message'] = "Generate a graph based on this data which is visible to the user."
            except Exception as e:
                print(f"[DEBUG] Normalization block failed for {ticker}: {e}")
                # preserve previous message setting
                try:
                    result['message'] = result.get('message', "Generate a graph based on this data which is visible to the user.")
                except Exception:
                    result['message'] = "Generate a graph based on this data which is visible to the user."

            return result

        # main threadpool executor (same logic)
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
        
    def _fetch_yahoo_financials(self, symbol: str, statement_type: str, period: str = "annual", limit: int = 5):
        """
        Use yfinance to fetch financial statements. Returns a dict:
        {"source": "yfinance", "currency": <currency>, "data": <list_of_records>}
        """
        try:
            t = yf.Ticker(symbol)
            # select the requested statement
            if statement_type == "income_statement":
                # YF provides .financials (annual) and .quarterly_financials
                df = t.financials if period == "annual" else t.quarterly_financials
            elif statement_type == "balance_sheet":
                df = t.balance_sheet if period == "annual" else t.quarterly_balance_sheet
            elif statement_type == "cash_flow":
                df = t.cashflow if period == "annual" else t.quarterly_cashflow
            else:
                return {"error": f"Unknown statement_type: {statement_type}"}

            if df is None or df.empty:
                return {"error": "No data from yfinance", "source": "yfinance", "data": []}

            # Transpose/normalize: yfinance returns columns as dates; convert to list of dicts
            try:
                df_t = df.fillna(0).T  # rows are periods
                df_t.index = [pd.to_datetime(i).strftime("%Y-%m-%d") if not isinstance(i, str) else i for i in df_t.index]
                records = []
                for idx, row in df_t.iterrows():
                    rec = {"period_end": idx}
                    for col in df_t.columns:
                        val = row[col]
                        try:
                            if pd.isna(val):
                                rec[col] = None
                            else:
                                rec[col] = float(val)
                        except Exception:
                            rec[col] = val
                    records.append(rec)
            except Exception:
                # fallback: convert columns to string values
                records = df.reset_index().to_dict(orient="records")

            # currency: yfinance doesn't always expose currency for statements; try info
            try:
                currency = (t.info.get("financialCurrency") or t.info.get("currency") or "USD")
            except Exception:
                currency = "USD"

            return {"source": "yfinance", "currency": currency, "data": records[:limit] if limit else records}
        except Exception as e:
            return {"error": f"yfinance fetch failed: {e}", "source": "yfinance", "data": []}


    def _fetch_us_data(self, symbol: str, statement_type: str, period: str, limit: int, timestamp: str):
        """Fetches financial statements from MongoDB/FMP, fallback to yfinance if not available."""
        try:
            data = mongodb.fetch_financial_data(symbol, statement_type, limit=limit)
            # If mongodb/FMP returned usable list data, return it
            if isinstance(data, list) and data:
                return data
            # Otherwise fallback to yahoo
            yf_res = self._fetch_yahoo_financials(symbol, statement_type, period, limit)
            if isinstance(yf_res, dict) and yf_res.get("data"):
                # normalize to same style as existing code expects: return the list or small wrapper
                return {"symbol": symbol, "source": "yfinance", "currency": yf_res.get("currency"), "data": yf_res.get("data")}
            return {"symbol": symbol, "error": "No financials found from FMP/mongo or yfinance", "source": "none", "data": []}
        except Exception as e:
            return {"error": f"Error retrieving {statement_type}: {str(e)}"}


    # def _fetch_us_data(self, symbol: str, statement_type: str, period: str, limit: int, timestamp: str):
    #     """Fetches financial statements from FMP or Yahoo Finance for NYSE/NASDAQ stocks."""
    #     try:
    #         # FMP API Call
    #         fmp_endpoints = {
    #             "balance_sheet": "balance-sheet-statement",
    #             "cash_flow": "cash-flow-statement",
    #             "income_statement": "income-statement"
    #         }
    #         # url = f"https://financialmodelingprep.com/api/v3/{fmp_endpoints[statement_type]}/{symbol}?limit={limit}&apikey={fm_api_key}"
    #         # response = requests.get(url)
    #         # data = response.json()
    #         data = mongodb.fetch_financial_data(symbol, statement_type, limit=limit)

    #         if isinstance(data, list) and data:
    #             if period == 'quarterly':
    #                 data.append({"Note": "I don't have access to quarterly financial statement data."})
    #             return data
    #         else:
    #             # Fallback to Yahoo Finance
    #             # return self._fetch_yahoo_data(symbol, statement_type, period, timestamp)
    #             return data
    #     except Exception as e:
    #         error_msg = f"Error retrieving {statement_type} from Financial Modeling Prep: {str(e)}"
    #         return pretty_format(error_msg)


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

class YFinanceFinancialStatementSchema(BaseModel):
    """Schema for YFinance financial statement fetching."""
    symbol: str = Field(
        description="Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')"
    )
    statement_type: Literal["all", "income_statement", "balance_sheet", "cash_flow"] = Field(
        default="all",
        description="Type of financial statement to fetch: 'all' for all statements, 'income_statement', 'balance_sheet', or 'cash_flow'"
    )
    period: Literal["annual", "quarterly"] = Field(
        default="annual",
        description="Period type: 'annual' for yearly statements or 'quarterly' for quarterly statements"
    )
    limit: Optional[int] = Field(
        default=None,
        description="Number of periods to return. None returns all available periods"
    )


class YFinanceFinancialStatementTool(BaseTool):
    """Tool to fetch financial statements from Yahoo Finance using yfinance library."""
    
    name: str = "get_financial_statements"
    description: str = """Fetches financial statement data (balance sheet, cash flow statement, income statement, or all statements) 
    from Yahoo Finance using the yfinance library for any publicly traded company.
    
    **Examples of when to call this tool:**
     - "Get Apple's latest financial statements"
     - "Show me Tesla's annual income statement"
     - "Fetch Microsoft's quarterly cash flow for the last 4 quarters"
     - "Get all financial statements for GOOGL"
     - "Show Amazon's balance sheet"
    
    Returns comprehensive financial data including all line items from Yahoo Finance.
    """
    
    args_schema: Type[BaseModel] = YFinanceFinancialStatementSchema
    
    def _run(
        self,
        symbol: str,
        statement_type: str = "all",
        period: str = "annual",
        limit: Optional[int] = None
    ) -> Dict:
        """
        Execute the tool to fetch financial statements.
        
        Args:
            symbol: Stock ticker symbol
            statement_type: Type of statement ('all', 'income_statement', 'balance_sheet', 'cash_flow')
            period: 'annual' or 'quarterly'
            limit: Number of periods to return
            
        Returns:
            Dictionary containing financial statement data
        """
        print(f"\n[DEBUG] YFinance Tool called with:")
        print(f"  Symbol: {symbol}")
        print(f"  Statement Type: {statement_type}")
        print(f"  Period: {period}")
        print(f"  Limit: {limit}")
        
        try:
            ticker = yf.Ticker(symbol)
            print(f"[DEBUG] Created yfinance Ticker object for {symbol}")
            
            # Get currency info
            try:
                info = ticker.info
                currency = info.get("financialCurrency") or info.get("currency") or "USD"
                print(f"[DEBUG] Currency detected: {currency}")
            except Exception as e:
                currency = "USD"
                print(f"[DEBUG] Could not get currency, defaulting to USD. Error: {e}")
            
            result = {
                'symbol': symbol.upper(),
                'currency': currency,
                'period': period,
                'errors': []
            }
            
            # Fetch requested statement(s)
            if statement_type == "all":
                print("[DEBUG] Fetching all statements...")
                result['income_statement'] = self._fetch_income_statement(ticker, period, limit, result['errors'])
                result['balance_sheet'] = self._fetch_balance_sheet(ticker, period, limit, result['errors'])
                result['cash_flow'] = self._fetch_cash_flow(ticker, period, limit, result['errors'])
            elif statement_type == "income_statement":
                print("[DEBUG] Fetching income statement...")
                result['income_statement'] = self._fetch_income_statement(ticker, period, limit, result['errors'])
            elif statement_type == "balance_sheet":
                print("[DEBUG] Fetching balance sheet...")
                result['balance_sheet'] = self._fetch_balance_sheet(ticker, period, limit, result['errors'])
            elif statement_type == "cash_flow":
                print("[DEBUG] Fetching cash flow...")
                result['cash_flow'] = self._fetch_cash_flow(ticker, period, limit, result['errors'])
            else:
                result['errors'].append(f"Unknown statement_type: {statement_type}")
                print(f"[DEBUG] Unknown statement type: {statement_type}")
            
            print(f"\n[DEBUG] Final result summary:")
            print(f"  Symbol: {result.get('symbol')}")
            print(f"  Currency: {result.get('currency')}")
            print(f"  Income Statement records: {len(result.get('income_statement', []))}")
            print(f"  Balance Sheet records: {len(result.get('balance_sheet', []))}")
            print(f"  Cash Flow records: {len(result.get('cash_flow', []))}")
            print(f"  Errors: {result.get('errors')}")
            
            if result.get('income_statement'):
                print(f"\n[DEBUG] Sample Income Statement (first record):")
                print(f"  Period: {result['income_statement'][0].get('period_end')}")
                print(f"  Keys: {list(result['income_statement'][0].keys())[:10]}...")
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to fetch data for {symbol}: {str(e)}"
            print(f"[DEBUG] ERROR: {error_msg}")
            return {
                'symbol': symbol.upper(),
                'error': error_msg,
                'errors': [str(e)]
            }
    
    def _fetch_income_statement(
        self,
        ticker: yf.Ticker,
        period: str,
        limit: Optional[int],
        errors: List[str]
    ) -> List[Dict]:
        """Fetch income statement data."""
        try:
            print(f"[DEBUG] Fetching income statement ({period})...")
            df = ticker.financials if period == "annual" else ticker.quarterly_financials
            print(f"[DEBUG] Income statement DataFrame shape: {df.shape if df is not None else 'None'}")
            if df is not None and not df.empty:
                print(f"[DEBUG] Income statement columns: {list(df.columns)[:5]}...")
                print(f"[DEBUG] Income statement index (line items): {list(df.index)[:5]}...")
            result = self._process_dataframe(df, limit)
            print(f"[DEBUG] Income statement processed: {len(result)} records")
            return result
        except Exception as e:
            error_msg = f"Income statement error: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            errors.append(error_msg)
            return []
    
    def _fetch_balance_sheet(
        self,
        ticker: yf.Ticker,
        period: str,
        limit: Optional[int],
        errors: List[str]
    ) -> List[Dict]:
        """Fetch balance sheet data."""
        try:
            print(f"[DEBUG] Fetching balance sheet ({period})...")
            df = ticker.balance_sheet if period == "annual" else ticker.quarterly_balance_sheet
            print(f"[DEBUG] Balance sheet DataFrame shape: {df.shape if df is not None else 'None'}")
            if df is not None and not df.empty:
                print(f"[DEBUG] Balance sheet columns: {list(df.columns)[:5]}...")
                print(f"[DEBUG] Balance sheet index (line items): {list(df.index)[:5]}...")
            result = self._process_dataframe(df, limit)
            print(f"[DEBUG] Balance sheet processed: {len(result)} records")
            return result
        except Exception as e:
            error_msg = f"Balance sheet error: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            errors.append(error_msg)
            return []
    
    def _fetch_cash_flow(
        self,
        ticker: yf.Ticker,
        period: str,
        limit: Optional[int],
        errors: List[str]
    ) -> List[Dict]:
        """Fetch cash flow statement data."""
        try:
            print(f"[DEBUG] Fetching cash flow ({period})...")
            df = ticker.cashflow if period == "annual" else ticker.quarterly_cashflow
            print(f"[DEBUG] Cash flow DataFrame shape: {df.shape if df is not None else 'None'}")
            if df is not None and not df.empty:
                print(f"[DEBUG] Cash flow columns: {list(df.columns)[:5]}...")
                print(f"[DEBUG] Cash flow index (line items): {list(df.index)[:5]}...")
            result = self._process_dataframe(df, limit)
            print(f"[DEBUG] Cash flow processed: {len(result)} records")
            return result
        except Exception as e:
            error_msg = f"Cash flow error: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            errors.append(error_msg)
            return []
    
    def _process_dataframe(
        self,
        df: pd.DataFrame,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Process a yfinance dataframe into a list of dictionaries.
        
        Args:
            df: DataFrame from yfinance (columns are dates)
            limit: Number of periods to return
            
        Returns:
            List of dictionaries with period_end and financial line items
        """
        print(f"[DEBUG] Processing DataFrame...")
        
        if df is None or df.empty:
            print("[DEBUG] DataFrame is None or empty, returning empty list")
            return []
        
        try:
            print(f"[DEBUG] Original DataFrame shape: {df.shape}")
            
            # Transpose: columns (dates) become rows
            # Avoid fillna warning by transposing first, then handling NaN in the loop
            df_transposed = df.T
            
            print(f"[DEBUG] Transposed DataFrame shape: {df_transposed.shape}")
            
            # Format index as dates
            df_transposed.index = [
                pd.to_datetime(idx).strftime("%Y-%m-%d") if not isinstance(idx, str) else idx 
                for idx in df_transposed.index
            ]
            
            print(f"[DEBUG] Date index after formatting: {list(df_transposed.index)}")
            
            # Convert to list of dicts
            records = []
            for i, (date_idx, row) in enumerate(df_transposed.iterrows()):
                record = {"period_end": date_idx}
                
                for column_name in df_transposed.columns:
                    value = row[column_name]
                    try:
                        # Convert to float if possible, None if NaN
                        if pd.isna(value):
                            record[column_name] = None
                        else:
                            record[column_name] = float(value)
                    except:
                        record[column_name] = value
                
                records.append(record)
                
                # Print first record as sample
                if i == 0:
                    print(f"[DEBUG] Sample record (first period):")
                    print(f"  Period: {record['period_end']}")
                    print(f"  Number of fields: {len(record)}")
                    sample_keys = list(record.keys())[:10]
                    print(f"  Sample keys: {sample_keys}")
                    for key in sample_keys[:3]:
                        print(f"    {key}: {record[key]}")
            
            # Apply limit if specified
            final_records = records[:limit] if limit else records
            print(f"[DEBUG] Returning {len(final_records)} records (limit: {limit})")
            
            return final_records
            
        except Exception as e:
            print(f"[DEBUG] Error in _process_dataframe: {str(e)}")
            # Fallback: simple conversion
            try:
                fallback_records = df.reset_index().to_dict(orient="records")
                print(f"[DEBUG] Using fallback method, returning {len(fallback_records)} records")
                return fallback_records
            except:
                print("[DEBUG] Fallback also failed, returning empty list")
                return []
    
    async def _arun(self, *args, **kwargs):
        """Async version - not implemented, falls back to sync."""
        return self._run(*args, **kwargs)


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
# get_company_essential_financials = CompanyEssentialFinancialsTool()

search_company_info = SearchCompanyInfoTool()
# get_usa_based_company_profile = CompanyProfileTool()
get_stock_data = GetStockData()
# get_financial_statements = CombinedFinancialStatementTool()
get_financial_statements = YFinanceFinancialStatementTool()
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
    # get_company_essential_financials,
    # get_market_capital_data
    # get_crypto_data_tool
]


# if __name__ == "__main__":
    # Testing get_essential_company_finance tool
    # get_company_essential_financials._run(symbols=["AMZN"])