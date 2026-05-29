"""
Analyze SP500 stocks: EMA proximity, price trends, and emerging momentum.
Outputs a coworker-friendly summary for further insights.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

COLUMN_ALIASES = {
    "Company": ["Company", "company"],
    "Sector": ["Sector", "sector"],
    "Industry": ["Industry", "industry"],
    "Price": ["Price", "price"],
    "Market Cap": ["Market Cap", "market_cap", "Mkt Cap"],
    "P/E": ["P/E", "pe", "PE"],
    "Forward P/E": ["Forward P/E", "Fwd P/E", "forward_pe"],
    "PEG": ["PEG", "peg"],
    "EPS (ttm)": ["EPS (ttm)", "EPS", "eps_ttm"],
    "EPS next Y": ["EPS next Y", "EPS Next Y", "eps_next_y"],
    "EPS next Y": ["EPS next Y", "EPS Next Y", "eps_next_y", "EPS Growth Next Year"],
    "ROE": ["ROE", "roe", "Return on Equity"],
    "ROA": ["ROA", "roa", "Return on Assets"],
    "Profit Margin": ["Profit Margin", "profit_margin"],
    "Debt/Eq": ["Debt/Eq", "debt_eq", "Debt/Equity", "Total Debt/Equity"],
    "RSI (14)": ["RSI (14)", "RSI", "rsi", "Relative Strength Index (14)"],
    "SMA20": ["SMA20", "sma20", "SMA 20", "20-Day Simple Moving Average"],
    "SMA50": ["SMA50", "sma50", "SMA 50", "50-Day Simple Moving Average"],
    "SMA200": ["SMA200", "sma200", "SMA 200", "200-Day Simple Moving Average"],
    "EMA20": ["EMA20", "ema20", "EMA 20", "20-Day Exponential Moving Average"],
    "EMA50": ["EMA50", "ema50", "EMA 50", "50-Day Exponential Moving Average"],
    "EMA200": ["EMA200", "ema200", "EMA 200", "200-Day Exponential Moving Average"],
    "200-Day SMA (Relative)": [
        "200-Day SMA (Relative)",
        "SMA200 (Relative)",
        "200-Day Simple Moving Average (Relative)",
    ],
    "Beta": ["Beta", "beta"],
    "ATR": ["ATR", "atr", "Average True Range"],
    "Volatility": ["Volatility", "volatility", "Volatility W", "Volatility (Week)"],
    "Rel Volume": ["Rel Volume", "Relative Volume", "rel_volume"],
    "Perf Week": ["Perf Week", "perf_week", "Perf W", "Performance (Week)"],
    "Perf Month": ["Perf Month", "perf_month", "Perf M", "Performance (Month)"],
    "Perf Quarter": ["Perf Quarter", "perf_quarter", "Perf Q", "Performance (Quarter)"],
    "Perf Half Y": ["Perf Half Y", "perf_half_y", "Perf HY", "Performance (Half Year)"],
    "Perf Year": ["Perf Year", "perf_year", "Perf Y", "Performance (Year)"],
    "Perf YTD": ["Perf YTD", "perf_ytd", "Performance (YTD)"],
    "Recom": ["Recom", "recom", "Recommendation", "Analyst Recom"],
    "Target Price": ["Target Price", "target_price"],
    "P/S": ["P/S", "ps"],
    "P/B": ["P/B", "pb"],
    "P/FCF": ["P/FCF", "p_fcf", "P/Free Cash Flow"],
    "Short Float": ["Short Float", "short_float"],
    "Change": ["Change", "change"],
}


def fv_get(data: dict, canonical_key: str, default=None):
    """Look up a value using canonical key or any known alias."""
    aliases = COLUMN_ALIASES.get(canonical_key, [canonical_key])
    for alias in aliases:
        if alias in data:
            return data[alias]
    return data.get(canonical_key, default)


def parse_pct(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace("%", ""))
    except (ValueError, TypeError):
        return None


def parse_number(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        s = str(val).replace(",", "").replace("%", "")
        if s == "-":
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def compute_ema(closes: list[float], period: int) -> float | None:
    """Standard daily EMA: seed with SMA of first `period` closes, then exponential smoothing."""
    if len(closes) < period:
        return None
    multiplier = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    for close in closes[period:]:
        ema = (close - ema) * multiplier + ema
    return round(ema, 4)


def ema200_from_polygon(polygon_entry: dict | None) -> dict | None:
    """Compute daily EMA200 and price distance from Polygon adjusted daily closes."""
    if not polygon_entry:
        return None
    bars = polygon_entry.get("results", [])
    period = config.POLYGON_EMA200_PERIOD
    if len(bars) < period:
        return None

    closes = [float(b["close"]) for b in bars]
    ema200 = compute_ema(closes, period)
    if ema200 is None or ema200 == 0:
        return None

    last_close = closes[-1]
    distance_pct = round(((last_close - ema200) / ema200) * 100, 2)
    return {
        "ema200": ema200,
        "last_close": round(last_close, 4),
        "last_date": bars[-1].get("date"),
        "distance_pct": distance_pct,
        "abs_distance_pct": round(abs(distance_pct), 2),
        "bars_used": len(closes),
        "source": "polygon",
    }


def apply_polygon_ema200(ema_data: dict, polygon_entry: dict | None) -> dict | None:
    """Prefer Polygon-computed EMA200; returns the metrics dict when applied."""
    polygon_ema = ema200_from_polygon(polygon_entry)
    if not polygon_ema:
        if ema_data.get("EMA200_pct_from_price") is not None:
            ema_data["EMA200_source"] = "finviz"
        return None

    ema_data["EMA200_pct_from_price"] = polygon_ema["distance_pct"]
    ema_data["EMA200_abs_distance_pct"] = polygon_ema["abs_distance_pct"]
    ema_data["EMA200_value"] = polygon_ema["ema200"]
    ema_data["EMA200_last_close"] = polygon_ema["last_close"]
    ema_data["EMA200_last_date"] = polygon_ema["last_date"]
    ema_data["EMA200_bars_used"] = polygon_ema["bars_used"]
    ema_data["EMA200_source"] = "polygon"
    return polygon_ema


def ema200_distance_pct(finviz_entry: dict) -> float | None:
    """
    Signed % distance of price from daily EMA200 (or 200-day MA relative from Finviz).
    Positive = price above EMA200; negative = price below.
    """
    price = parse_number(fv_get(finviz_entry, "Price"))
    if price is None or price == 0:
        return None

    # Finviz relative columns: already "% from MA" (price vs moving average)
    for key in (
        "EMA200",
        "200-Day Exponential Moving Average",
        "200-Day SMA (Relative)",
        "SMA200",
    ):
        raw = fv_get(finviz_entry, key)
        if raw is None:
            continue
        pct = parse_pct(raw)
        if pct is None:
            continue
        # Relative Finviz fields are small %; absolute MA levels are near price magnitude
        if abs(pct) <= 50 or "%" in str(raw):
            return round(pct, 2)
        if pct > 0:
            return round(((price - pct) / pct) * 100, 2)

    # Scan any column Finviz may label differently on export
    for key, val in finviz_entry.items():
        if val is None or key == "ticker":
            continue
        kl = str(key).lower()
        if "200" not in kl or not any(x in kl for x in ("ema", "sma", "moving", "relative")):
            continue
        pct = parse_pct(val)
        if pct is not None and abs(pct) <= 50:
            return round(pct, 2)

    return None


def is_near_ema200_daily(distance_pct: float | None) -> bool:
    """True when |distance from daily EMA200| is within configured min/max % band."""
    if distance_pct is None:
        return False
    adist = abs(distance_pct)
    return config.EMA200_NEAR_PCT_MIN <= adist <= config.EMA200_NEAR_PCT_MAX


def compute_ema_proximity(finviz_entry: dict) -> dict:
    """How close is the current price to EMA20/50/200. Falls back to SMA if EMA not available."""
    price = parse_number(fv_get(finviz_entry, "Price"))
    if price is None or price == 0:
        return {}

    proximities = {}
    ema_sma_pairs = [
        ("EMA20", "SMA20"),
        ("EMA50", "SMA50"),
    ]
    for ema_key, sma_key in ema_sma_pairs:
        raw = fv_get(finviz_entry, ema_key)
        if raw is None:
            raw = fv_get(finviz_entry, sma_key)
        pct = parse_pct(raw)
        if pct is not None and abs(pct) <= 50:
            proximities[f"{ema_key}_pct_from_price"] = round(pct, 2)

    ema200_dist = ema200_distance_pct(finviz_entry)
    if ema200_dist is not None:
        proximities["EMA200_pct_from_price"] = ema200_dist
        proximities["EMA200_abs_distance_pct"] = round(abs(ema200_dist), 2)

    return proximities


def polygon_entry_for_trend(polygon_entry: dict | None) -> dict | None:
    """Use only the recent LOOKBACK_DAYS bars for short-term trend metrics."""
    if not polygon_entry:
        return None
    bars = polygon_entry.get("results", [])
    if not bars:
        return None
    if len(bars) > config.LOOKBACK_DAYS:
        bars = bars[-config.LOOKBACK_DAYS :]
    return {"ticker": polygon_entry.get("ticker"), "results": bars}


def compute_price_trend(polygon_entry: dict) -> dict:
    """Compute simple trend metrics from daily bars."""
    bars = polygon_entry.get("results", [])
    if len(bars) < 2:
        return {}

    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]

    first_close = closes[0]
    last_close = closes[-1]
    total_return = round(((last_close - first_close) / first_close) * 100, 2) if first_close else 0

    max_close = max(closes)
    min_close = min(closes)
    price_range_pct = round(((max_close - min_close) / min_close) * 100, 2) if min_close else 0

    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    recent_vol = volumes[-1] if volumes else 0
    vol_trend = round((recent_vol / avg_volume - 1) * 100, 2) if avg_volume else 0

    up_days = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
    down_days = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i - 1])

    consecutive_up = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i - 1]:
            consecutive_up += 1
        else:
            break

    return {
        "period_return_pct": total_return,
        "price_range_pct": price_range_pct,
        "up_days": up_days,
        "down_days": down_days,
        "consecutive_up_days": consecutive_up,
        "volume_trend_pct": vol_trend,
        "latest_close": last_close,
        "period_high": max_close,
        "period_low": min_close,
        "num_bars": len(bars),
    }


def score_emerging_trend(ema_data: dict, trend_data: dict, finviz_data: dict) -> float:
    """
    Score 0-100 for emerging improvement signal. Higher = more interesting.
    Factors: EMA proximity, recent return, volume pickup, RSI recovery, consecutive ups.
    """
    score = 50.0

    ema20_pct = ema_data.get("EMA20_pct_from_price")
    if ema20_pct is not None:
        if -3 <= ema20_pct <= 3:
            score += 10
        if ema20_pct > 0:
            score += 5

    ema50_pct = ema_data.get("EMA50_pct_from_price")
    if ema50_pct is not None:
        if -3 <= ema50_pct <= 3:
            score += 8
        if ema50_pct > 0:
            score += 4

    ema200_pct = ema_data.get("EMA200_pct_from_price")
    if ema200_pct is not None:
        if is_near_ema200_daily(ema200_pct):
            score += 12
        elif ema200_pct > 0:
            score += 5

    ret = trend_data.get("period_return_pct", 0)
    if ret > 0:
        score += min(ret * 2, 15)
    elif ret < -5:
        score -= 10

    consec = trend_data.get("consecutive_up_days", 0)
    score += min(consec * 3, 12)

    vol = trend_data.get("volume_trend_pct", 0)
    if vol > 20:
        score += 8
    elif vol > 0:
        score += 4

    rsi = parse_number(fv_get(finviz_data, "RSI (14)"))
    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 6
        elif 30 <= rsi < 40:
            score += 10
        elif rsi < 30:
            score += 8

    return round(min(max(score, 0), 100), 1)


def classify_ema_position(ema_data: dict) -> str:
    """Classify the stock's position relative to its EMAs."""
    ema20 = ema_data.get("EMA20_pct_from_price")
    ema50 = ema_data.get("EMA50_pct_from_price")
    ema200 = ema_data.get("EMA200_pct_from_price")

    if ema20 is None:
        return "unknown"

    near_ema20 = ema20 is not None and abs(ema20) <= 2
    near_ema50 = ema50 is not None and abs(ema50) <= 2
    near_ema200 = is_near_ema200_daily(ema200)

    above_all = all(
        v is not None and v > 0
        for v in [ema20, ema50, ema200]
        if v is not None
    )

    if near_ema20 and near_ema50:
        return "converging_near_ema20_ema50"
    if near_ema200:
        return "near_ema200_daily"
    if near_ema20:
        return "near_ema20"
    if near_ema50:
        return "near_ema50"
    if above_all:
        return "above_all_emas"
    return "below_key_emas"


def analyze_all(polygon_data: list[dict], finviz_data: list[dict]) -> list[dict]:
    finviz_map = {d["ticker"]: d for d in finviz_data}
    polygon_map = {d["ticker"]: d for d in polygon_data}

    all_tickers = set(finviz_map.keys()) | set(polygon_map.keys())
    results = []

    for ticker in sorted(all_tickers):
        fv = finviz_map.get(ticker, {})
        pg = polygon_map.get(ticker, {})

        ema_data = compute_ema_proximity(fv)
        polygon_ema200 = apply_polygon_ema200(ema_data, pg)
        ema200_dist = ema_data.get("EMA200_pct_from_price")
        near_ema200 = is_near_ema200_daily(ema200_dist)
        trend_data = compute_price_trend(polygon_entry_for_trend(pg) or {}) if pg else {}
        trend_score = score_emerging_trend(ema_data, trend_data, fv)
        ema_position = classify_ema_position(ema_data)

        price = parse_number(fv_get(fv, "Price"))
        if polygon_ema200:
            price = polygon_ema200["last_close"]

        entry = {
            "ticker": ticker,
            "company": fv_get(fv, "Company", ""),
            "sector": fv_get(fv, "Sector", ""),
            "industry": fv_get(fv, "Industry", ""),
            "price": price,
            "market_cap": fv_get(fv, "Market Cap", ""),

            "ema_position": ema_position,
            "ema_proximity": ema_data,
            "near_ema200_daily": near_ema200,
            "ema200_distance_pct": ema200_dist,
            "ema200_source": ema_data.get("EMA200_source"),
            "ema200_polygon": polygon_ema200,

            "trend": trend_data,

            "fundamentals": {
                "pe": fv_get(fv, "P/E"),
                "forward_pe": fv_get(fv, "Forward P/E"),
                "peg": fv_get(fv, "PEG"),
                "eps_ttm": fv_get(fv, "EPS (ttm)"),
                "eps_growth_next_y": fv_get(fv, "EPS next Y"),
                "roe": fv_get(fv, "ROE"),
                "profit_margin": fv_get(fv, "Profit Margin"),
                "debt_equity": fv_get(fv, "Debt/Eq"),
            },

            "technicals": {
                "rsi_14": fv_get(fv, "RSI (14)"),
                "sma20": fv_get(fv, "SMA20"),
                "sma50": fv_get(fv, "SMA50"),
                "sma200": fv_get(fv, "SMA200"),
                "ema20": fv_get(fv, "EMA20"),
                "ema50": fv_get(fv, "EMA50"),
                "ema200": (
                    ema_data.get("EMA200_value")
                    if ema_data.get("EMA200_source") == "polygon"
                    else fv_get(fv, "EMA200")
                ),
                "beta": fv_get(fv, "Beta"),
                "atr": fv_get(fv, "ATR"),
                "volatility": fv_get(fv, "Volatility"),
                "rel_volume": fv_get(fv, "Rel Volume"),
            },

            "performance": {
                "week": fv_get(fv, "Perf Week"),
                "month": fv_get(fv, "Perf Month"),
                "quarter": fv_get(fv, "Perf Quarter"),
                "half_year": fv_get(fv, "Perf Half Y"),
                "year": fv_get(fv, "Perf Year"),
                "ytd": fv_get(fv, "Perf YTD"),
            },

            "analyst": {
                "recommendation": fv_get(fv, "Recom"),
                "target_price": fv_get(fv, "Target Price"),
            },

            "finviz_raw": {k: v for k, v in fv.items() if k != "ticker"},

            "emerging_trend_score": trend_score,
        }

        results.append(entry)

    results.sort(key=lambda x: x["emerging_trend_score"], reverse=True)
    return results


def filter_near_ema200_daily(analyzed: list[dict]) -> list[dict]:
    """All stocks with daily price within configured % band of EMA200."""
    hits = [s for s in analyzed if s.get("near_ema200_daily")]
    hits.sort(
        key=lambda x: x.get("ema_proximity", {}).get("EMA200_abs_distance_pct", 999),
    )
    return hits


def generate_coworker_summary(analyzed: list[dict]) -> dict:
    """Create a structured summary optimized for a coworker agent to consume."""

    near_ema200_daily = filter_near_ema200_daily(analyzed)
    ema200_polygon_count = sum(1 for s in analyzed if s.get("ema200_source") == "polygon")
    ema200_finviz_count = sum(
        1 for s in analyzed if s.get("ema200_source") == "finviz" and s.get("ema200_distance_pct") is not None
    )

    near_ema = [s for s in analyzed if s["ema_position"] in (
        "near_ema20", "near_ema50", "converging_near_ema20_ema50", "near_ema200_daily"
    )]

    top_emerging = [s for s in analyzed if s["emerging_trend_score"] >= 70]

    sector_groups = {}
    for s in analyzed:
        sec = s.get("sector", "Unknown")
        if sec not in sector_groups:
            sector_groups[sec] = {"count": 0, "avg_score": 0, "top_tickers": []}
        sector_groups[sec]["count"] += 1
        sector_groups[sec]["avg_score"] += s["emerging_trend_score"]

    for sec in sector_groups:
        g = sector_groups[sec]
        g["avg_score"] = round(g["avg_score"] / g["count"], 1)
        sec_stocks = [s for s in analyzed if s.get("sector") == sec]
        sec_stocks.sort(key=lambda x: x["emerging_trend_score"], reverse=True)
        g["top_tickers"] = [
            {"ticker": s["ticker"], "score": s["emerging_trend_score"], "ema_position": s["ema_position"]}
            for s in sec_stocks[:5]
        ]

    return {
        "metadata": {
            "total_stocks_analyzed": len(analyzed),
            "lookback_days": config.LOOKBACK_DAYS,
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "data_sources": ["Polygon.io (OHLCV daily bars)", "Finviz (fundamentals + technicals + EMA)"],
            "ema200_near_band_pct": {
                "min": config.EMA200_NEAR_PCT_MIN,
                "max": config.EMA200_NEAR_PCT_MAX,
                "description": (
                    f"Price within {config.EMA200_NEAR_PCT_MIN}%–{config.EMA200_NEAR_PCT_MAX}% "
                    "of daily EMA200 (absolute distance)."
                ),
            },
            "ema200_computation": {
                "primary": "polygon_daily_closes",
                "period": config.POLYGON_EMA200_PERIOD,
                "polygon_lookback_calendar_days": config.POLYGON_EMA200_LOOKBACK_DAYS,
                "tickers_with_polygon_ema200": ema200_polygon_count,
                "tickers_with_finviz_fallback": ema200_finviz_count,
            },
        },
        "executive_summary": {
            "stocks_near_ema": len(near_ema),
            "stocks_near_ema200_daily": len(near_ema200_daily),
            "top_emerging_count": len(top_emerging),
            "description": (
                f"Out of {len(analyzed)} SP500 stocks, {len(near_ema200_daily)} are within "
                f"{config.EMA200_NEAR_PCT_MIN}%–{config.EMA200_NEAR_PCT_MAX}% of daily EMA200, "
                f"{len(near_ema)} are near key EMAs overall, and {len(top_emerging)} show strong "
                "emerging trend signals (score >= 70)."
            ),
        },
        "stocks_near_ema200_daily": [
            {
                "ticker": s["ticker"],
                "company": s["company"],
                "sector": s["sector"],
                "price": s["price"],
                "ema200": s["technicals"].get("ema200") or s["technicals"].get("sma200"),
                "ema200_source": s.get("ema200_source"),
                "ema200_last_date": s.get("ema_proximity", {}).get("EMA200_last_date"),
                "ema200_distance_pct": s.get("ema200_distance_pct"),
                "ema200_abs_distance_pct": s.get("ema_proximity", {}).get("EMA200_abs_distance_pct"),
                "side_of_ema200": (
                    "above" if (s.get("ema200_distance_pct") or 0) > 0
                    else "below" if (s.get("ema200_distance_pct") or 0) < 0
                    else "at"
                ),
                "trend_score": s["emerging_trend_score"],
                "rsi": s["technicals"]["rsi_14"],
                "period_return": s["trend"].get("period_return_pct"),
            }
            for s in near_ema200_daily
        ],
        "stocks_near_emas": [
            {
                "ticker": s["ticker"],
                "company": s["company"],
                "sector": s["sector"],
                "price": s["price"],
                "ema_position": s["ema_position"],
                "ema_proximity": s["ema_proximity"],
                "trend_score": s["emerging_trend_score"],
                "rsi": s["technicals"]["rsi_14"],
                "period_return": s["trend"].get("period_return_pct"),
                "volume_trend": s["trend"].get("volume_trend_pct"),
            }
            for s in near_ema
        ],
        "top_emerging_trends": [
            {
                "ticker": s["ticker"],
                "company": s["company"],
                "sector": s["sector"],
                "price": s["price"],
                "trend_score": s["emerging_trend_score"],
                "ema_position": s["ema_position"],
                "ema_proximity": s["ema_proximity"],
                "fundamentals": s["fundamentals"],
                "technicals": s["technicals"],
                "performance": s["performance"],
                "trend": s["trend"],
                "analyst": s["analyst"],
            }
            for s in top_emerging[:30]
        ],
        "sector_heatmap": sector_groups,
        "all_stocks_ranked": [
            {
                "ticker": s["ticker"],
                "company": s["company"],
                "sector": s["sector"],
                "price": s["price"],
                "trend_score": s["emerging_trend_score"],
                "ema_position": s["ema_position"],
                "rsi": s["technicals"]["rsi_14"],
                "period_return": s["trend"].get("period_return_pct"),
            }
            for s in analyzed
        ],
    }


def save_analysis(analyzed: list[dict], summary: dict, output_dir: str = None):
    if output_dir is None:
        output_dir = config.OUTPUT_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    full_path = Path(output_dir) / "full_analysis.json"
    with open(full_path, "w") as f:
        json.dump(analyzed, f, indent=2)
    print(f"Saved full analysis ({len(analyzed)} stocks) to {full_path}")

    summary_path = Path(output_dir) / "coworker_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved coworker summary to {summary_path}")

    ema200_path = Path(output_dir) / "stocks_near_ema200_daily.json"
    ema200_payload = {
        "metadata": summary.get("metadata", {}).get("ema200_near_band_pct", {}),
        "count": len(summary.get("stocks_near_ema200_daily", [])),
        "stocks": summary.get("stocks_near_ema200_daily", []),
    }
    with open(ema200_path, "w") as f:
        json.dump(ema200_payload, f, indent=2)
    print(f"Saved {ema200_payload['count']} EMA200-near stocks to {ema200_path}")

    return full_path, summary_path
