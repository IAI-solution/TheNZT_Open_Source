# chart_bot/moving_average.py
"""
Simple Moving Average (SMA) tool — FMP-first.

Primary source:
  • FMP /stable/technical-indicators/sma

Fallback (daily only, still FMP-only):
  • Compute SMA locally from FMP /stable/historical-price-eod/full closes.

Behavior highlights:
  • Returns newest-first time series for each requested period.
  • Handles 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS'.
  • on_date: daily → nearest prior trading day; intraday → last bar that day; else nearest prior bar.
  • Optional crossover detection: "golden" (short crosses above long) / "death" (short crosses below long).
  • Invalid calendar dates (e.g., 2025-02-29) are coerced to the last valid day of the month (2025-02-28) and noted.
  • Provenance notes show source per period.

Return shape:
{
  "symbol": "...",
  "timeframe": "1day",
  "period_lengths": [10, 50, 200],
  "requested_window": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "series": { "10":[{"date":"...","sma":float}, ...], "50":[...], ... },  # newest-first
  "on_date": { "10":{"date_requested":"...","date_used":"...","sma":float,"sma_rounded":float}, ... } | {},
  "crossovers": [ {"date":"YYYY-MM-DD","type":"golden"|"death"}, ... ],
  "notes": [ ... ]
}
"""

from __future__ import annotations

import os
import asyncio
import calendar
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime, date, timedelta
from statistics import fmean
from datetime import datetime, timezone
import httpx
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from dotenv import load_dotenv
load_dotenv()

# ---------- Env & constants ----------
FM_API_KEY = os.getenv("FM_API_KEY")

FMP_SMA_URL = "https://financialmodelingprep.com/stable/technical-indicators/sma"
FMP_EOD_URL = "https://financialmodelingprep.com/stable/historical-price-eod/full"

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)
RETRY_STATUS = {429, 500, 502, 503, 504}


# ---------- Small HTTP helper ----------

async def _get_with_retries(client: httpx.AsyncClient, url: str, params: Dict[str, Any], tries: int = 3, backoff: float = 0.75) -> httpx.Response:
    for i in range(tries):
        try:
            resp = await client.get(url, params=params)
            if resp.status_code in RETRY_STATUS:
                raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.HTTPError):
            if i == tries - 1:
                raise
            await asyncio.sleep(backoff * (2 ** i))


# ---------- Helpers ----------

def _parse_iso(d: str) -> date:
    """Parse 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' to date."""
    return datetime.strptime(d[:10], "%Y-%m-%d").date()

def _fmt_iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def _coerce_to_prior_valid_calendar_date(s: str) -> str:
    """
    Accepts 'YYYY-MM-DD' (or with time). If the calendar date is invalid
    (e.g., 2025-02-29), coerce to the last valid day of that month (2025-02-28).
    Returns 'YYYY-MM-DD'. Raises ValueError if Y/M/D cannot be parsed at all.
    """
    raw = s[:10]
    try:
        _ = datetime.strptime(raw, "%Y-%m-%d").date()
        return raw
    except ValueError:
        pass
    y, m, d = map(int, raw.split("-"))
    if not (1 <= m <= 12):
        raise ValueError(f"Invalid month in date: {s}")
    last_day = calendar.monthrange(y, m)[1]
    d = min(max(1, d), last_day)
    return f"{y:04d}-{m:02d}-{d:02d}"

def _find_on_or_before(target: date, series_newest_first: List[Dict[str, Any]], key: str = "sma") -> Optional[Dict[str, Any]]:
    """Series expected newest-first. Return the first row with row_date <= target and key present."""
    for row in series_newest_first:
        try:
            row_date = _parse_iso(row.get("date"))
        except Exception:
            continue
        if row_date <= target and row.get(key) is not None:
            return row
    return None

def _extract_historical(payload: Any) -> Optional[List[Dict[str, Any]]]:
    """
    Normalize FMP SMA payload to list[{date, sma}].
    FMP variants:
      - {"historical": [...]}
      - {"data": [...]}
    Fields: "sma" or "value"
    """
    raw = None
    if isinstance(payload, dict):
        raw = payload.get("historical") or payload.get("data")
    elif isinstance(payload, list):
        raw = payload
    if not raw or not isinstance(raw, list):
        return None

    out: List[Dict[str, Any]] = []
    for row in raw:
        d = row.get("date")
        s = row.get("sma", row.get("value"))
        if d and s is not None:
            try:
                out.append({"date": d, "sma": float(s)})
            except Exception:
                continue
    return out

async def _fallback_sma_from_eod(
    client: httpx.AsyncClient,
    symbol: str,
    period: int,
    _from: Optional[str],
    _to: Optional[str],
) -> Optional[List[Dict[str, Any]]]:
    """
    Fallback (daily only): compute SMA from FMP EOD closes.
    Returns newest-first SMA series.
    """
    params = {"symbol": symbol, "apikey": FM_API_KEY}
    if _from:
        params["from"] = _from
    if _to:
        params["to"] = _to

    r = await _get_with_retries(client, FMP_EOD_URL, params)
    data = r.json() or {}
    hist = data.get("historical")
    if not hist or not isinstance(hist, list):
        return None

    asc = sorted(
        (
            {"date": h.get("date"), "close": h.get("close")}
            for h in hist
            if h.get("date") and h.get("close") is not None
        ),
        key=lambda x: x["date"],
    )
    if len(asc) < period:
        return None

    closes = [float(x["close"]) for x in asc]
    dates = [x["date"] for x in asc]

    points: List[Dict[str, Any]] = []
    for i in range(period - 1, len(closes)):
        wnd = closes[i - period + 1 : i + 1]
        sma = fmean(wnd)
        points.append({"date": dates[i], "sma": float(sma)})

    return sorted(points, key=lambda x: x["date"], reverse=True)

def _detect_crossovers(
    short_series: List[Dict[str, Any]],
    long_series: List[Dict[str, Any]],
    mode: Literal["golden", "death"],
) -> List[Dict[str, Any]]:
    """
    Detect crossovers on dates present in BOTH series.
    Input lists are newest-first; we align by date and scan in ASC order.
    """
    s_map = {r["date"]: r.get("sma") for r in short_series if r.get("date") and r.get("sma") is not None}
    l_map = {r["date"]: r.get("sma") for r in long_series if r.get("date") and r.get("sma") is not None}
    common = sorted(set(s_map.keys()) & set(l_map.keys()))  # ASC

    events: List[Dict[str, Any]] = []
    prev_diff: Optional[float] = None
    for d in common:
        s = s_map[d]; l = l_map[d]
        diff = s - l
        if prev_diff is not None:
            if mode == "golden" and prev_diff <= 0 and diff > 0:
                events.append({"date": d, "type": "golden"})
            if mode == "death" and prev_diff >= 0 and diff < 0:
                events.append({"date": d, "type": "death"})
        prev_diff = diff
    return events

def _clip_events_to_window(events: List[Dict[str, Any]], _from: Optional[str], _to: Optional[str]) -> List[Dict[str, Any]]:
    if not events or (not _from and not _to):
        return events
    lo = _parse_iso(_from) if _from else None
    hi = _parse_iso(_to) if _to else None
    out: List[Dict[str, Any]] = []
    for e in events:
        try:
            d = _parse_iso(e["date"])
        except Exception:
            continue
        if lo and d < lo:
            continue
        if hi and d > hi:
            continue
        out.append(e)
    return out


# ---------- Input schema ----------

Timeframe = Literal["1min","5min","15min","30min","1hour","4hour","1day","1week","1month"]

class SMAInput(BaseModel):
    symbol: str = Field(..., description="Stock ticker, e.g., 'TSLA'.")
    period_lengths: List[int] = Field(..., description="SMA periods, e.g., [10] or [50, 200].")
    timeframe: Timeframe = "1day"
    on_date: Optional[str] = Field(None, description="YYYY-MM-DD. If non-trading (daily), uses prior trading day.")
    from_date: Optional[str] = Field(None, description="YYYY-MM-DD. Start of range.")
    to_date: Optional[str] = Field(None, description="YYYY-MM-DD. End of range.")
    crossover_mode: Optional[Literal["golden","death"]] = Field(None, description="Set for crossover detection; requires exactly two periods.")

    @field_validator("period_lengths")
    @classmethod
    def _not_empty(cls, v):
        if not v:
            raise ValueError("period_lengths must contain at least one value.")
        return v

    @field_validator("on_date", "from_date", "to_date")
    @classmethod
    def _normalize_dates(cls, v):
        if v is None:
            return v
        # Coerce invalid calendar dates to prior valid day
        return _coerce_to_prior_valid_calendar_date(v)


# ---------- Tool ----------

@tool(args_schema=SMAInput)
async def fetch_sma_from_fmp(
    symbol: str,
    period_lengths: List[int],
    timeframe: Timeframe = "1day",
    on_date: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    crossover_mode: Optional[Literal["golden","death"]] = None,
) -> Dict[str, Any]:
    """
    Fetch SMA from FMP (endpoint-first). Fallback computes SMA from FMP EOD closes (daily only).
    Returns newest-first series per period, on_date values, optional crossovers, and provenance notes.
    """
    if not FM_API_KEY:
        return {"error": "FM_API_KEY environment variable is not set."}

    symbol = symbol.upper().strip()
    period_lengths = [int(p) for p in period_lengths]

    # Normalize and possibly note invalid calendar date for on_date
    coerced_on_date = None
    if on_date:
        coerced_on_date = _coerce_to_prior_valid_calendar_date(on_date)
        if coerced_on_date != on_date[:10]:
            # Make the adjustment visible to the agent/UX
            # e.g., "Requested 2025-02-29 is not a valid calendar date; used 2025-02-28."
            note = f"Requested {on_date[:10]} is not a valid calendar date; used {coerced_on_date}."
            # We'll append after out is created.

    # --- Auto range resolution ---
    today = datetime.now(timezone.utc).date() 
    _from, _to = (from_date, to_date)

    if coerced_on_date and (not _from or not _to):
        target = _parse_iso(coerced_on_date)
        window_days = max(400, max(period_lengths) * 5)
        _from = _from or _fmt_iso(target - timedelta(days=window_days))
        _to = _to or _fmt_iso(target)

    if crossover_mode and (not _from or not _to):
        _from = _from or _fmt_iso(today - timedelta(days=600))
        _to = _to or _fmt_iso(today)

    # If both from/to provided but reversed, swap and note
    swapped_range_note = None
    if _from and _to and _parse_iso(_from) > _parse_iso(_to):
        _from, _to = _to, _from
        swapped_range_note = f"Swapped from/to to maintain chronological order: from={_from}, to={_to}."

    common_params = {"symbol": symbol, "timeframe": timeframe, "apikey": FM_API_KEY}
    if _from:
        common_params["from"] = _from
    if _to:
        common_params["to"] = _to

    out: Dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "period_lengths": period_lengths,
        "series": {},
        "on_date": {},
        "crossovers": [],
        "requested_window": {"from": _from, "to": _to},
        "notes": [],
    }

    # Append notes captured before out existed
    if on_date and coerced_on_date and coerced_on_date != on_date[:10]:
        out["notes"].append(f"Requested {on_date[:10]} is not a valid calendar date; used {coerced_on_date}.")
    if swapped_range_note:
        out["notes"].append(swapped_range_note)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            # For each period, call SMA endpoint; if empty and timeframe==1day, compute from EOD.
            for p in period_lengths:
                params = dict(common_params)
                params["periodLength"] = p

                historical: Optional[List[Dict[str, Any]]] = None
                try:
                    resp = await _get_with_retries(client, FMP_SMA_URL, params)
                    data = resp.json()
                    historical = _extract_historical(data)
                    if historical:
                        historical = sorted(historical, key=lambda x: x["date"], reverse=True)
                        out["notes"].append(f"Used FMP SMA technical-indicators endpoint for {p}-period.")
                except Exception:
                    historical = None

                if (not historical or len(historical) == 0) and timeframe == "1day":
                    fb = await _fallback_sma_from_eod(client, symbol, p, _from, _to)
                    if fb:
                        historical = fb
                        out["notes"].append(f"Computed {p}-day SMA from FMP EOD closes due to sparse SMA endpoint data.")

                if not historical:
                    if timeframe != "1day":
                        return {"error": f"No SMA data returned for the requested intraday timeframe from FMP (period {p}). Try widening the range or use 1day."}
                    return {"error": f"No SMA data returned for period {p} in the requested window. Try widening the range."}

                out["series"][str(p)] = historical  # newest-first

            # on_date resolution
            if coerced_on_date:
                target_date = _parse_iso(coerced_on_date)
                for p_str, ser in out["series"].items():
                    if timeframe == "1day":
                        row = _find_on_or_before(target_date, ser, key="sma")
                        used = row["date"] if row else None
                        out["on_date"][p_str] = {
                            "date_requested": on_date,  # show original
                            "date_used": used,
                            "sma": row["sma"] if row else None,
                            "sma_rounded": round(row["sma"], 2) if row and row.get("sma") is not None else None,
                        }
                        if used and used[:10] != coerced_on_date:
                            out["notes"].append(f"Requested {coerced_on_date} was non-trading; used prior trading day {used[:10]}.")
                    else:
                        # pick the most recent bar on that calendar day
                        day_prefix = coerced_on_date
                        same_day_rows = [
                            r for r in ser
                            if isinstance(r.get("date"), str) and r["date"].startswith(day_prefix) and r.get("sma") is not None
                        ]
                        row = same_day_rows[0] if same_day_rows else None
                        used = row["date"] if row else None
                        if not row:
                            prior = next(
                                (r for r in ser if isinstance(r.get("date"), str) and r["date"][:10] < coerced_on_date and r.get("sma") is not None),
                                None
                            )
                            if prior:
                                row = prior
                                used = row["date"]
                                out["notes"].append(f"No intraday bars on {coerced_on_date}; used nearest prior bar {used}.")
                        out["on_date"][p_str] = {
                            "date_requested": on_date,  # original input
                            "date_used": used,
                            "sma": row["sma"] if row else None,
                            "sma_rounded": round(row["sma"], 2) if row and row.get("sma") is not None else None,
                        }

            # crossovers
            if crossover_mode and len(period_lengths) == 2:
                short_p, long_p = sorted(period_lengths)
                short_series = out["series"].get(str(short_p), [])
                long_series  = out["series"].get(str(long_p), [])
                events = _detect_crossovers(short_series, long_series, crossover_mode)
                events = _clip_events_to_window(events, _from, _to)
                out["crossovers"] = events

        return out

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except httpx.HTTPError as e:
        return {"error": f"Network error while fetching SMA: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error while fetching SMA: {e}"}
