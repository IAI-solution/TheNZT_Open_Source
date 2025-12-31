# chart_bot/price_change.py
import os
import asyncio
import datetime as dt
from typing import Optional, Dict, Any, Tuple, List

import httpx
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()
fm_api_key = os.getenv("FM_API_KEY")

# Optional dependency: yfinance
try:
    import yfinance as yf
    _HAS_YF = True
except Exception:
    _HAS_YF = False


class PriceChangeInput(BaseModel):
    """Input schema for the price change tool."""
    ticker: str = Field(..., description="Stock ticker symbol, e.g., 'AAPL'.")
    from_date: str = Field(..., description="Start date (YYYY-MM-DD).")
    to_date: str = Field(..., description="End date (YYYY-MM-DD).")


def _parse_date(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%Y-%m-%d").date()


def _pick_price_bar(bar: Dict[str, Any]) -> Optional[float]:
    # Prefer adjusted if present; fallback to close.
    for k in ("adjClose", "adjustedClose", "Adj Close", "adj_close", "close", "Close"):
        if k in bar and isinstance(bar[k], (int, float)):
            return float(bar[k])
    return None


def _compute_change(start_price: float, end_price: float) -> Dict[str, Any]:
    delta = end_price - start_price
    pct = (delta / start_price) * 100 if start_price else None
    return {"start_price": start_price, "end_price": end_price, "change": delta, "change_pct": pct}


async def _fetch_fmp_range(
    ticker: str, from_date: str, to_date: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not fm_api_key:
        return None, "Missing FM_API_KEY for FMP source"

    # base = "https://financialmodelingprep.com/api/v3"
    # url = f"{base}/historical-price-full/{ticker}"
    base = "https://financialmodelingprep.com/stable"
    url = f"{base}/historical-price-eod/full?symbol={ticker}"
    params = {"apikey": fm_api_key, "from": from_date, "to": to_date}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return None, f"FMP request failed: {e}"

    hist = data.get("historical") or []
    if not isinstance(hist, list) or not hist:
        return None, "FMP returned no historical data for the range"

    # FMP usually returns most-recent-first; sort ascending by date
    try:
        hist.sort(key=lambda x: x.get("date"))
    except Exception:
        pass

    start_bar = hist[0]
    end_bar = hist[-1]

    sp = _pick_price_bar(start_bar)
    ep = _pick_price_bar(end_bar)
    if sp is None or ep is None:
        return None, "FMP data missing close/adjusted fields"

    return {
        "source": "fmp",
        "symbol": ticker,
        "from": start_bar.get("date"),
        "to": end_bar.get("date"),
        **_compute_change(sp, ep),
    }, None


async def _fetch_yf_range(
    ticker: str, from_date: str, to_date: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not _HAS_YF:
        return None, "yfinance is not installed"

    start = _parse_date(from_date)
    end_inclusive = _parse_date(to_date)
    # yfinance 'end' is exclusive; add one day so the given 'to_date' is included
    end_exclusive = end_inclusive + dt.timedelta(days=1)

    def _dl():
        return yf.download(
            ticker,
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            progress=False,
            auto_adjust=False,
            threads=False,
        )

    try:
        df = await asyncio.to_thread(_dl)
    except Exception as e:
        return None, f"Yahoo download failed: {e}"

    if df is None or df.empty:
        return None, "Yahoo returned no data for the range"

    # Prefer Adjusted Close if available
    col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)
    if col is None:
        return None, "Yahoo data missing Close/Adj Close columns"

    start_ts = df.index[0]
    end_ts = df.index[-1]
    sp = float(df.iloc[0][col])
    ep = float(df.iloc[-1][col])

    return {
        "source": "yahoo",
        "symbol": ticker,
        "from": str(start_ts.date()),
        "to": str(end_ts.date()),
        **_compute_change(sp, ep),
    }, None


@tool(args_schema=PriceChangeInput)
async def calculate_price_change(ticker: str, from_date: str, to_date: str) -> Dict[str, Any]:
    """
    Calculate absolute and percentage price change for a stock over a date range.
    Uses FMP if FM_API_KEY is set; otherwise falls back to Yahoo Finance (yfinance).
    Returns a dict with fields: source, symbol, from, to, start_price, end_price, change, change_pct.
    """
    # Basic date validation
    try:
        start = _parse_date(from_date)
        end = _parse_date(to_date)
        if start > end:
            return {"error": "from_date must be on or before to_date"}
    except Exception:
        return {"error": "Dates must be in YYYY-MM-DD format"}

    if fm_api_key:
        data, err = await _fetch_fmp_range(ticker, from_date, to_date)
        if data:
            return data
        # If FMP failed, try Yahoo as safety net
        yf_data, yf_err = await _fetch_yf_range(ticker, from_date, to_date)
        return yf_data or {"error": f"FMP failed: {err}; Yahoo fallback failed: {yf_err}"}
    else:
        # No FMP key: use Yahoo directly
        data, err = await _fetch_yf_range(ticker, from_date, to_date)
        return data or {"error": err}
