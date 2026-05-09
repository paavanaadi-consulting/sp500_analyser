"""
Analyze SP500 stocks: EMA proximity, price trends, and emerging momentum.
Outputs a coworker-friendly summary for further insights.
"""
from __future__ import annotations

import json
from pathlib import Path

import config

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
    "ROE": ["ROE", "roe"],
    "Profit Margin": ["Profit Margin", "profit_margin"],
    "Debt/Eq": ["Debt/Eq", "debt_eq", "Debt/Equity"],
    "RSI (14)": ["RSI (14)", "RSI", "rsi"],
    "SMA20": ["SMA20", "sma20", "SMA 20"],
    "SMA50": ["SMA50", "sma50", "SMA 50"],
    "SMA200": ["SMA200", "sma200", "SMA 200"],
    "EMA20": ["EMA20", "ema20", "EMA 20"],
    "EMA50": ["EMA50", "ema50", "EMA 50"],
    "EMA200": ["EMA200", "ema200", "EMA 200"],
    "Beta": ["Beta", "beta"],
    "ATR": ["ATR", "atr"],
    "Volatility": ["Volatility", "volatility", "Volatility W"],
    "Rel Volume": ["Rel Volume", "Relative Volume", "rel_volume"],
    "Perf Week": ["Perf Week", "perf_week", "Perf W"],
    "Perf Month": ["Perf Month", "perf_month", "Perf M"],
    "Perf Quarter": ["Perf Quarter", "perf_quarter", "Perf Q"],
    "Perf Half Y": ["Perf Half Y", "perf_half_y", "Perf HY"],
    "Perf Year": ["Perf Year", "perf_year", "Perf Y"],
    "Perf YTD": ["Perf YTD", "perf_ytd"],
    "Recom": ["Recom", "recom", "Recommendation"],
    "Target Price": ["Target Price", "target_price"],
    "P/S": ["P/S", "ps"],
    "P/B": ["P/B", "pb"],
    "P/FCF": ["P/FCF", "p_fcf"],
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


def compute_ema_proximity(finviz_entry: dict) -> dict:
    """How close is the current price to EMA20, EMA50, EMA200 (from Finviz)."""
    price = parse_number(fv_get(finviz_entry, "Price"))
    if price is None or price == 0:
        return {}

    proximities = {}
    for ema_key in ["EMA20", "EMA50", "EMA200"]:
        raw = fv_get(finviz_entry, ema_key)
        pct = parse_pct(raw)
        if pct is not None:
            proximities[f"{ema_key}_pct_from_price"] = round(pct, 2)

    return proximities


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
        if ema200_pct > 0:
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
    near_ema200 = ema200 is not None and abs(ema200) <= 3

    above_all = all(
        v is not None and v > 0
        for v in [ema20, ema50, ema200]
        if v is not None
    )

    if near_ema20 and near_ema50:
        return "converging_near_ema20_ema50"
    if near_ema200:
        return "testing_ema200_support"
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
        trend_data = compute_price_trend(pg) if pg else {}
        trend_score = score_emerging_trend(ema_data, trend_data, fv)
        ema_position = classify_ema_position(ema_data)

        entry = {
            "ticker": ticker,
            "company": fv_get(fv, "Company", ""),
            "sector": fv_get(fv, "Sector", ""),
            "industry": fv_get(fv, "Industry", ""),
            "price": parse_number(fv_get(fv, "Price")),
            "market_cap": fv_get(fv, "Market Cap", ""),

            "ema_position": ema_position,
            "ema_proximity": ema_data,

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
                "ema200": fv_get(fv, "EMA200"),
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


def generate_coworker_summary(analyzed: list[dict]) -> dict:
    """Create a structured summary optimized for a coworker agent to consume."""

    near_ema = [s for s in analyzed if s["ema_position"] in (
        "near_ema20", "near_ema50", "converging_near_ema20_ema50", "testing_ema200_support"
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
        },
        "executive_summary": {
            "stocks_near_ema": len(near_ema),
            "top_emerging_count": len(top_emerging),
            "description": (
                f"Out of {len(analyzed)} SP500 stocks, {len(near_ema)} are near key EMAs "
                f"and {len(top_emerging)} show strong emerging trend signals (score >= 70). "
                "Stocks near EMAs may be at inflection points — worth deeper analysis."
            ),
        },
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

    return full_path, summary_path
