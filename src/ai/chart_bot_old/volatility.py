"""
Volatility tool (FMP-first).
Computes and returns historical volatility (σ) using Financial Modeling Prep's
standard deviation endpoint, with a returns-based fallback (from FMP EOD closes)
ONLY if the endpoint yields no usable rows (daily timeframe).

Outputs both:
  • $ standard deviation (endpoint value)
  • Daily % σ = (standardDeviation / close) × 100
Optionally: Annualized % σ = Daily % × √trading_days (default 252)

Return shape fits LangChain tool usage and is easy for the agent to narrate.
"""
from __future__ import annotations

import os
import math
from typing import List, Dict, Optional, Literal, Any, Tuple
from datetime import datetime, date, timedelta
from statistics import stdev
from datetime import datetime, timezone
import httpx
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from langchain_core.tools import tool

# -------- Env --------
load_dotenv()
FM_API_KEY = os.getenv("FM_API_KEY")

# -------- Constants --------
FMP_STD_URL = "https://financialmodelingprep.com/stable/technical-indicators/standarddeviation"
FMP_EOD_URL = "https://financialmodelingprep.com/stable/historical-price-eod/full"
DEFAULT_TIMEOUT = 30.0


# ================= Helpers ================= #

def _parse_iso(d: str) -> date:
    """Parse 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' to date."""
    return datetime.strptime(d[:10], "%Y-%m-%d").date()


def _fmt_iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _extract_std_series(payload: Any) -> Optional[List[Dict[str, Any]]]:
    """
    Normalize FMP stddev payload to a list[{date, vol_raw, close}]:
      - vol_raw: $ standard deviation from the endpoint
      - close: close price if present (some payloads omit it)
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
        v = row.get("standardDeviation", row.get("value"))
        c = row.get("close")
        if d and v is not None:
            try:
                out.append(
                    {
                        "date": d,
                        "vol_raw": float(v),
                        "close": float(c) if c is not None else None,
                    }
                )
            except Exception:
                continue
    return out


async def _fetch_close_map(
    client: httpx.AsyncClient,
    symbol: str,
    _from: Optional[str],
    _to: Optional[str],
) -> Dict[str, float]:
    """Build {YYYY-MM-DD -> close} from FMP EOD endpoint."""
    params = {"symbol": symbol, "apikey": FM_API_KEY}
    if _from:
        params["from"] = _from
    if _to:
        params["to"] = _to

    try:
        r = await client.get(FMP_EOD_URL, params=params)
        r.raise_for_status()
        data = r.json() or {}
        hist = data.get("historical") or []
        out: Dict[str, float] = {}
        for row in hist:
            d = row.get("date")
            c = row.get("close")
            if d and c is not None:
                try:
                    out[d[:10]] = float(c)
                except Exception:
                    continue
        return out
    except Exception:
        return {}


def _nearest_prior_close(date_str: str, close_map: Dict[str, float]) -> Optional[float]:
    """Pick the nearest prior trading day's close."""
    d = _parse_iso(date_str)
    for k in sorted(close_map.keys(), reverse=True):
        try:
            dk = _parse_iso(k)
        except Exception:
            continue
        if dk <= d:
            return close_map[k]
    return None


async def _fallback_std_from_eod(
    client: httpx.AsyncClient,
    symbol: str,
    period: int,
    _from: Optional[str],
    _to: Optional[str],
    returns_type: Literal["log", "pct"] = "log",
) -> Optional[List[Dict[str, Any]]]:
    """
    Daily-only fallback: compute rolling σ of returns from FMP EOD closes.
    Returns newest-first list of {date, close, vol (daily %), vol_raw ($ approx)}.
    """
    params = {"symbol": symbol, "apikey": FM_API_KEY}
    if _from:
        params["from"] = _from
    if _to:
        params["to"] = _to

    r = await client.get(FMP_EOD_URL, params=params)
    r.raise_for_status()
    data = r.json() or {}
    hist = data.get("historical")
    if not hist:
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
    dates = [x["date"] for x in asc]

    rets: List[float] = []
    for i in range(1, len(closes)):
        if returns_type == "log":
            rets.append(0.0 if closes[i - 1] <= 0 else math.log(closes[i] / closes[i - 1]))
        else:
            rets.append((closes[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] != 0 else 0.0)

    if len(rets) < period:
        return None

    out: List[Dict[str, Any]] = []
    for i in range(period - 1, len(rets)):
        wnd = rets[i - period + 1 : i + 1]
        try:
            sigma = stdev(wnd)  # fraction (e.g., 0.023)
        except Exception:
            continue
        d_i = dates[i + 1]
        c_i = closes[i + 1]
        out.append(
            {
                "date": d_i,
                "close": c_i,
                "vol": float(sigma * 100.0),  # daily %
                "vol_raw": float(sigma * c_i),  # $ approx
            }
        )

    return sorted(out, key=lambda x: x["date"], reverse=True)


def _count_days(series: List[Dict[str, Any]], cmp: str, thr: float) -> int:
    cnt = 0
    for row in series:
        v = row.get("vol")
        if v is None:
            continue
        if (cmp == "gt" and v > thr) or (cmp == "ge" and v >= thr) or (cmp == "lt" and v < thr) or (cmp == "le" and v <= thr):
            cnt += 1
    return cnt


def _streak(series_asc: List[Dict[str, Any]], cmp: str, thr: float) -> Tuple[int, Optional[str], Optional[str]]:
    """Longest streak in ASC order meeting a condition on percent vol."""
    best = 0
    cur = 0
    start: Optional[str] = None
    best_range = (None, None)
    for row in series_asc:
        v = row.get("vol")
        d = row.get("date")
        ok = (cmp == "gt" and v > thr) or (cmp == "ge" and v >= thr) or (cmp == "lt" and v < thr) or (cmp == "le" and v <= thr)
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
    """Detect crossings vs a percent threshold level."""
    up: List[str] = []
    down: List[str] = []
    prev: Optional[float] = None
    for row in series_asc:
        v = row.get("vol")
        if v is None:
            continue
        if prev is not None:
            if prev <= level and v > level:
                up.append(row["date"])
            if prev >= level and v < level:
                down.append(row["date"])
        prev = v
    return {"crossed_up": up, "crossed_down": down}


def _annualize_pct(vol_pct_daily: Optional[float], timeframe: str, trading_days: int) -> Optional[float]:
    if vol_pct_daily is None or timeframe != "1day":
        return None
    return float((vol_pct_daily / 100.0) * math.sqrt(trading_days) * 100.0)


# ================= Input Schema ================= #

class VolatilityInput(BaseModel):
    symbol: str = Field(..., description="Ticker, e.g., 'TSLA'.")
    period_lengths: List[int] = Field(..., description="Window lengths, e.g., [10], [20, 60].")
    timeframe: Literal["1min", "5min", "15min", "30min", "1hour", "4hour", "1day", "1week", "1month"] = "1day"
    on_date: Optional[str] = Field(None, description="YYYY-MM-DD. Daily uses prior trading day if needed; intraday uses last bar.")
    from_date: Optional[str] = Field(None, description="YYYY-MM-DD. Range start.")
    to_date: Optional[str] = Field(None, description="YYYY-MM-DD. Range end.")
    thresholds: Optional[List[float]] = Field(default_factory=list, description="Daily % thresholds, e.g., [3, 5].")
    annualize: bool = Field(False, description="If True (daily), include annualized % (× √trading_days).")
    trading_days: int = Field(252, description="Trading days per year.")
    returns_type: Literal["log", "pct"] = Field("log", description="Fallback only: log or percent returns.")

    @field_validator("period_lengths")
    def _not_empty(cls, v):
        if not v:
            raise ValueError("period_lengths must contain at least one value.")
        return v

    @field_validator("on_date", "from_date", "to_date")
    def _validate_date(cls, v):
        if v is None:
            return v
        _ = _parse_iso(v)
        return v


# ================= Tool ================= #

@tool(args_schema=VolatilityInput)
async def fetch_volatility_from_fmp(
    symbol: str,
    period_lengths: List[int],
    timeframe: str = "1day",
    on_date: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    thresholds: Optional[List[float]] = None,
    annualize: bool = False,
    trading_days: int = 252,
    returns_type: str = "log",
) -> Dict[str, Any]:
    """
    Fetch rolling volatility (σ) from FMP's standardDeviation endpoint.

    Returns:
      {
        symbol, timeframe, requested_window: {from, to},
        series: {
          "10": [ {date, close, vol_raw ($), vol (%), vol_annualized (%?)}, ... ],
          "20": ...
        },
        on_date: {
          "10": {date_requested, date_used, close, vol_raw, vol, vol_annualized?},
          ...
        },
        thresholds, signals (counts/crossings/streaks), extremes (max/min %),
        notes: [provenance strings]
      }
    """
    if not FM_API_KEY:
        return {"error": "FM_API_KEY environment variable is not set."}

    thresholds = thresholds or []

    # --- Resolve default window ---
    today = datetime.now(timezone.utc).date() 
    _from, _to = (from_date, to_date)

    if on_date and (not _from or not _to):
        target = _parse_iso(on_date)
        window_days = max(400, max(period_lengths) * 5)
        _from = _from or _fmt_iso(target - timedelta(days=window_days))
        _to = _to or _fmt_iso(target)

    if not _from and not _to:
        _from = _fmt_iso(today - timedelta(days=365))
        _to = _fmt_iso(today)

    common = {"symbol": symbol, "timeframe": timeframe, "apikey": FM_API_KEY}
    if _from:
        common["from"] = _from
    if _to:
        common["to"] = _to

    out: Dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "requested_window": {"from": _from, "to": _to},
        "series": {},
        "on_date": {},
        "thresholds": thresholds,
        "signals": {},
        "extremes": {},
        "notes": [],
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            for p in period_lengths:
                params = dict(common)
                params["periodLength"] = p

                # ---- Primary: FMP stddev endpoint ----
                resp = await client.get(FMP_STD_URL, params=params)
                raw_series: Optional[List[Dict[str, Any]]] = None
                try:
                    resp.raise_for_status()
                    raw_series = _extract_std_series(resp.json())
                except Exception:
                    raw_series = None

                ser: List[Dict[str, Any]] = []

                if raw_series:
                    need_close = any(r.get("close") in (None, 0) for r in raw_series)
                    close_map: Dict[str, float] = {}
                    if need_close and timeframe == "1day":
                        # widen by ±3 days to fill gaps
                        map_from = _fmt_iso(_parse_iso(_from) - timedelta(days=3)) if _from else None
                        map_to = _fmt_iso(_parse_iso(_to) + timedelta(days=3)) if _to else None
                        close_map = await _fetch_close_map(client, symbol, map_from, map_to)

                    for r in raw_series:
                        dt = r["date"]
                        close = r.get("close")
                        if (close is None or close == 0) and timeframe == "1day":
                            close = close_map.get(dt[:10]) or _nearest_prior_close(dt, close_map)

                        vol_raw = r.get("vol_raw")  # $ σ from endpoint
                        vol_pct: Optional[float] = None
                        if close and close != 0 and vol_raw is not None:
                            vol_pct = float(vol_raw / close * 100.0)

                        row = {"date": dt, "close": close, "vol_raw": vol_raw, "vol": vol_pct}
                        if annualize and timeframe == "1day" and vol_pct is not None:
                            row["vol_annualized"] = _annualize_pct(vol_pct, timeframe, trading_days)
                        ser.append(row)

                    if ser:
                        out["notes"].append(f"Used FMP standardDeviation endpoint for {p}-period volatility.")

                # ---- Fallback: returns-based (daily only) ----
                if not ser and timeframe == "1day":
                    fb = await _fallback_std_from_eod(client, symbol, p, _from, _to, returns_type=returns_type)
                    if fb:
                        if annualize:
                            for r in fb:
                                r["vol_annualized"] = _annualize_pct(r.get("vol"), timeframe, trading_days)
                        ser = fb
                        out["notes"].append(
                            f"No usable stddev rows from endpoint; computed {p}-period volatility from FMP EOD closes (returns-based)."
                        )

                if not ser:
                    return {
                        "error": f"No volatility data returned for period {p}. Try daily timeframe or widen the date range."
                    }

                ser = sorted(ser, key=lambda x: x["date"], reverse=True)
                out["series"][str(p)] = ser

            # ---- on_date selection ----
            if on_date:
                for p_str, ser in out["series"].items():
                    used: Optional[str] = None
                    sel: Optional[Dict[str, Any]] = None
                    if timeframe == "1day":
                        # Prefer rows that have % σ; if absent, allow rows with only $ σ.
                        target = _parse_iso(on_date)
                        sel = next(
                            (row for row in ser if _parse_iso(row["date"]) <= target and row.get("vol") is not None),
                            None,
                        ) or next(
                            (row for row in ser if _parse_iso(row["date"]) <= target and row.get("vol_raw") is not None),
                            None,
                        )
                        if sel:
                            used = sel["date"]
                            if used[:10] != on_date:
                                out["notes"].append(
                                    f"Requested {on_date} was non-trading or missing; used prior trading day {used[:10]}."
                                )
                            if sel.get("close") is None:
                                out["notes"].append("Backfilled close from FMP EOD to compute percent volatility.")
                    else:
                        # Intraday: newest bar on that calendar day; else nearest prior bar
                        same_day = [
                            r for r in ser if isinstance(r.get("date"), str) and r["date"].startswith(on_date) and
                            (r.get("vol") is not None or r.get("vol_raw") is not None)
                        ]
                        sel = same_day[0] if same_day else None
                        used = sel["date"] if sel else None
                        if not sel:
                            prior = next(
                                (
                                    r
                                    for r in ser
                                    if r.get("date") and r["date"][:10] < on_date and
                                    (r.get("vol") is not None or r.get("vol_raw") is not None)
                                ),
                                None,
                            )
                            if prior:
                                sel = prior
                                used = sel["date"]
                                out["notes"].append(f"No intraday bars on {on_date}; used nearest prior bar {used}.")

                    on_obj = {
                        "date_requested": on_date,
                        "date_used": used,
                        "close": sel.get("close") if sel else None,
                        "vol_raw": sel.get("vol_raw") if sel else None,  # $ σ
                        "vol": sel.get("vol") if sel else None,          # daily %
                    }
                    if on_obj["vol"] is None and on_obj["vol_raw"] is not None and on_obj["close"]:
                        on_obj["vol"] = float(on_obj["vol_raw"] / on_obj["close"] * 100.0)
                    if annualize and timeframe == "1day" and on_obj.get("vol") is not None:
                        on_obj["vol_annualized"] = _annualize_pct(on_obj["vol"], timeframe, trading_days)

                    out["on_date"][p_str] = on_obj

            # ---- analytics: thresholds & extremes (percent scale) ----
            for p_str, ser in out["series"].items():
                ser_pct = [r for r in ser if r.get("vol") is not None]
                if not ser_pct:
                    continue

                asc = sorted(ser_pct, key=lambda x: x["date"])
                desc = ser_pct  # newest-first as stored

                signals = {"counts": {}, "crossings": {}, "streaks": {}}
                for t in thresholds:
                    signals["counts"][f"> {t}%"] = _count_days(desc, "gt", t)
                    signals["counts"][f"< {t}%"] = _count_days(desc, "lt", t)
                    signals["crossings"][f"{t}%"] = _threshold_crossings(asc, t)
                    L_hi, s_hi, e_hi = _streak(asc, "gt", t)
                    L_lo, s_lo, e_lo = _streak(asc, "lt", t)
                    signals["streaks"][f"> {t}%"] = {"length": L_hi, "start": s_hi, "end": e_hi}
                    signals["streaks"][f"< {t}%"] = {"length": L_lo, "start": s_lo, "end": e_lo}

                out["signals"][p_str] = signals

                max_row = max(ser_pct, key=lambda x: x["vol"])
                min_row = min(ser_pct, key=lambda x: x["vol"])
                out["extremes"][p_str] = {"max": max_row, "min": min_row}

        return out

    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except httpx.HTTPError as e:
        return {"error": f"Network error while fetching volatility: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error while fetching volatility: {e}"}
