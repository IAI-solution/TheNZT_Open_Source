# chart_bot/relative_strength.py
"""
RSI tool — FMP-first.

Primary source:
  • FMP /stable/technical-indicators/rsi

Fallback (daily only, still FMP-only):
  • Compute Wilder RSI locally from FMP /stable/historical-price-eod/full closes.

Behavior highlights:
  • Returns newest-first time series.
  • Handles 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS'.
  • on_date: daily → nearest prior trading day; intraday → last available bar that day, else nearest prior bar.
  • Invalid calendar dates (e.g., 2025-02-29) are coerced to the last valid day of that month and noted.
  • Signals: counts above/below thresholds, threshold crossings (ASC), longest streaks, extremes.
  • Provenance notes show whether RSI came from the RSI endpoint or was computed from EOD closes.

Return shape:
{
  "symbol": "...",
  "timeframe": "1day",
  "requested_window": {"from": "...", "to": "..."},
  "series": [{"date":"YYYY-MM-DD ...","rsi": float}, ...],  # newest-first
  "on_date": {"date_requested":"YYYY-MM-DD","date_used":"YYYY-MM-DD ...","rsi": float} | None,
  "thresholds": [30.0, 70.0],
  "signals": {
      "counts": {"> 70.0": N, "< 30.0": M, ...},
      "crossings": {"30.0":{"crossed_up":[...],"crossed_down":[...]}, ...},
      "streaks": {"gt_70.0":{"length":L,"start":d1,"end":d2}, "lt_30.0": {...}}
  },
  "extremes": {"max":{"date":...,"rsi":...},"min":{"date":...,"rsi":...}},
  "notes": [...]
}
"""

from __future__ import annotations

import os
import asyncio
import calendar
from typing import List, Dict, Optional, Literal, Any, Tuple
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
FMP_RSI_URL = "https://financialmodelingprep.com/stable/technical-indicators/rsi"
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
    (e.g., 2025-02-29), coerce to the last valid day of that month.
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

def _extract_rsi_series(payload: Any) -> Optional[List[Dict[str, Any]]]:
    """
    Normalize FMP RSI payload to list[{date, rsi}].
    FMP variants:
      - {"historical": [...]}
      - {"data": [...]}
    Fields: "rsi" or "value"
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
        v = row.get("rsi", row.get("value"))
        if d and v is not None:
            try:
                out.append({"date": d, "rsi": float(v)})
            except Exception:
                continue
    return out

def _find_on_or_before(target: date, series_newest_first: List[Dict[str, Any]], key: str = "rsi") -> Optional[Dict[str, Any]]:
    """Series expected newest-first. Return the first row with row_date <= target and key present."""
    for row in series_newest_first:
        try:
            row_date = _parse_iso(row.get("date"))
        except Exception:
            continue
        if row_date <= target and row.get(key) is not None:
            return row
    return None

def _count_days(series: List[Dict[str, Any]], op: Literal["gt","lt","ge","le"], threshold: float) -> int:
    cnt = 0
    for row in series:
        v = row.get("rsi")
        if v is None:
            continue
        if (op == "gt" and v > threshold) or (op == "lt" and v < threshold) or (op == "ge" and v >= threshold) or (op == "le" and v <= threshold):
            cnt += 1
    return cnt

def _streak(series_asc: List[Dict[str, Any]], op: Literal["gt","lt","ge","le"], threshold: float) -> Tuple[int, Optional[str], Optional[str]]:
    """Longest streak in ASC order meeting a condition. Returns (length, start_date, end_date)."""
    best = 0
    cur = 0
    best_range = (None, None)
    start = None
    for row in series_asc:
        v = row.get("rsi")
        d = row.get("date")
        ok = (op == "gt" and v > threshold) or (op == "lt" and v < threshold) or (op == "ge" and v >= threshold) or (op == "le" and v <= threshold)
        if ok:
            cur += 1
            if start is None:
                start = d
            if cur > best:
                best = cur
                best_range = (start, d)
        else:
            cur = 0
            start = None
    return best, best_range[0], best_range[1]

def _threshold_crossings(series_asc: List[Dict[str, Any]], level: float) -> Dict[str, List[str]]:
    """
    Detect crossings relative to a threshold level:
      - 'crossed_up': moved from <= level to > level
      - 'crossed_down': moved from >= level to < level
    Returns dict of date lists in ASC order.
    """
    up, down = [], []
    prev = None
    for row in series_asc:
        v = row.get("rsi")
        if v is None:
            continue
        if prev is not None:
            if prev <= level and v > level:
                up.append(row["date"])
            if prev >= level and v < level:
                down.append(row["date"])
        prev = v
    return {"crossed_up": up, "crossed_down": down}

async def _fallback_rsi_from_eod(
    client: httpx.AsyncClient,
    symbol: str,
    period: int,
    _from: Optional[str],
    _to: Optional[str],
) -> Optional[List[Dict[str, Any]]]:
    """
    Fallback (daily only): compute Wilder RSI from FMP EOD closes.
    Returns newest-first RSI series.
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
    if len(asc) <= period:
        return None

    closes = [float(x["close"]) for x in asc]
    dates  = [x["date"] for x in asc]

    # Wilder's RSI
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    # initial averages
    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])

    def _compute_rsi(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    rsi_points: List[Dict[str, Any]] = []
    rsi_points.append({"date": dates[period], "rsi": float(_compute_rsi(avg_gain, avg_loss))})

    # Wilder smoothing
    for i in range(period + 1, len(closes)):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi_points.append({"date": dates[i], "rsi": float(_compute_rsi(avg_gain, avg_loss))})

    return sorted(rsi_points, key=lambda x: x["date"], reverse=True)


# ---------- Input schema ----------

Timeframe = Literal["1min","5min","15min","30min","1hour","4hour","1day","1week","1month"]

class RSIInput(BaseModel):
    symbol: str = Field(..., description="Stock ticker, e.g., 'TSLA'.")
    period_length: int = Field(14, description="RSI period length (default 14).")
    timeframe: Timeframe = "1day"
    on_date: Optional[str] = Field(None, description="YYYY-MM-DD. If non-trading, uses prior trading day.")
    from_date: Optional[str] = Field(None, description="YYYY-MM-DD. Start of range.")
    to_date: Optional[str] = Field(None, description="YYYY-MM-DD. End of range.")
    thresholds: Optional[List[float]] = Field(default_factory=lambda: [30.0, 70.0], description="Threshold levels (default [30, 70]).")

    @field_validator("on_date", "from_date", "to_date")
    @classmethod
    def _normalize_dates(cls, v):
        if v is None:
            return v
        # Coerce invalid calendar dates to prior valid day
        return _coerce_to_prior_valid_calendar_date(v)


# ---------- Tool ----------

@tool(args_schema=RSIInput)
async def fetch_rsi_from_fmp(
    symbol: str,
    period_length: int = 14,
    timeframe: Timeframe = "1day",
    on_date: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    thresholds: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Fetch RSI from FMP (endpoint-first). Fallback computes Wilder RSI from FMP EOD closes (daily only).
    Returns newest-first series plus analytics (counts, crossings, streaks, extremes) and provenance notes.
    """
    if not FM_API_KEY:
        return {"error": "FM_API_KEY environment variable is not set."}

    symbol = symbol.upper().strip()
    thresholds = thresholds or [30.0, 70.0]

    # Normalize and possibly note invalid calendar date for on_date
    coerced_on_date = None
    if on_date:
        coerced_on_date = _coerce_to_prior_valid_calendar_date(on_date)
        invalid_date_note = (coerced_on_date != on_date[:10])

    # --- Auto windowing ---
    today = datetime.now(timezone.utc).date() 
    _from, _to = (from_date, to_date)

    if coerced_on_date and (not _from or not _to):
        target = _parse_iso(coerced_on_date)
        window_days = max(200, period_length * 20)  # generous for intraday coverage
        _from = _from or _fmt_iso(target - timedelta(days=window_days))
        _to   = _to   or _fmt_iso(target)

    if not _from and not _to:
        _from = _fmt_iso(today - timedelta(days=365))
        _to   = _fmt_iso(today)

    # If both from/to provided but reversed, swap and note
    swapped_range_note = None
    if _from and _to and _parse_iso(_from) > _parse_iso(_to):
        _from, _to = _to, _from
        swapped_range_note = f"Swapped from/to to maintain chronological order: from={_from}, to={_to}."

    params_base = {"symbol": symbol, "timeframe": timeframe, "periodLength": period_length, "apikey": FM_API_KEY}
    if _from:
        params_base["from"] = _from
    if _to:
        params_base["to"] = _to

    out: Dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "series": [],
        "on_date": None,
        "thresholds": thresholds,
        "signals": {"counts": {}, "crossings": {}, "streaks": {}},
        "extremes": {},
        "requested_window": {"from": _from, "to": _to},
        "notes": [],
    }

    # Notes collected before out existed
    if on_date and coerced_on_date and invalid_date_note:
        out["notes"].append(f"Requested {on_date[:10]} is not a valid calendar date; used {coerced_on_date}.")
    if swapped_range_note:
        out["notes"].append(swapped_range_note)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            # 1) primary: RSI endpoint
            series = None
            try:
                resp = await _get_with_retries(client, FMP_RSI_URL, params_base)
                data = resp.json()
                series = _extract_rsi_series(data)
                if series:
                    series = sorted(series, key=lambda x: x["date"], reverse=True)
                    out["notes"].append(f"Used FMP RSI technical-indicators endpoint for period={period_length}.")
            except Exception:
                series = None

            # 2) fallback: compute from EOD (daily only)
            if (not series or len(series) == 0) and timeframe == "1day":
                fb = await _fallback_rsi_from_eod(client, symbol, period_length, _from, _to)
                if fb:
                    series = fb
                    out["notes"].append(
                        f"Computed RSI from FMP EOD closes for {symbol} {_from}→{_to} (period={period_length})."
                    )

            if not series:
                if timeframe != "1day":
                    return {"error": "No RSI data returned for the requested intraday timeframe from FMP. Try widening the range or use 1day."}
                return {"error": "No RSI data returned in the requested window. Try widening the range."}

            out["series"] = series  # newest-first

            # --- on_date resolution ---
            if coerced_on_date:
                used = None
                row = None
                if timeframe == "1day":
                    row = _find_on_or_before(_parse_iso(coerced_on_date), series, key="rsi")
                    used = row["date"] if row else None
                    if used and used[:10] != coerced_on_date:
                        out["notes"].append(f"Requested {coerced_on_date} was non-trading; used prior trading day {used[:10]}.")
                else:
                    # pick the most recent bar on that calendar day (i.e., the day's last bar)
                    day_prefix = coerced_on_date
                    same_day_rows = [
                        r for r in series
                        if isinstance(r.get("date"), str) and r["date"].startswith(day_prefix) and r.get("rsi") is not None
                    ]
                    row = same_day_rows[0] if same_day_rows else None
                    used = row["date"] if row else None
                    if not row:
                        # nearest prior bar in the series
                        prior = next(
                            (r for r in series if isinstance(r.get("date"), str) and r["date"][:10] < coerced_on_date and r.get("rsi") is not None),
                            None
                        )
                        if prior:
                            row = prior
                            used = row["date"]
                            out["notes"].append(f"No intraday bars on {coerced_on_date}; used nearest prior bar {used}.")

                out["on_date"] = {
                    "date_requested": on_date,   # original input
                    "date_used": used,
                    "rsi": row["rsi"] if row else None,
                }

            # --- analytics over the window ---
            desc = series
            asc = sorted(series, key=lambda x: x["date"])

            for t in thresholds:
                out["signals"]["counts"][f"> {t}"] = _count_days(desc, "gt", t)
                out["signals"]["counts"][f"< {t}"] = _count_days(desc, "lt", t)
                out["signals"]["crossings"][f"{t}"] = _threshold_crossings(asc, t)
                L, s, e = _streak(asc, "gt", t)
                out["signals"]["streaks"][f"gt_{t}"] = {"length": L, "start": s, "end": e}
                L, s, e = _streak(asc, "lt", t)
                out["signals"]["streaks"][f"lt_{t}"] = {"length": L, "start": s, "end": e}

            # extremes (guard for numeric)
            numeric = [r for r in desc if isinstance(r.get("rsi"), (int, float))]
            if not numeric:
                return {"error": "RSI series contained no numeric values."}
            max_row = max(numeric, key=lambda x: x["rsi"])
            min_row = min(numeric, key=lambda x: x["rsi"])
            out["extremes"] = {"max": max_row, "min": min_row}

        return out

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except httpx.HTTPError as e:
        return {"error": f"Network error while fetching RSI: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error while fetching RSI: {e}"}
