"""
Daily EMA200 alert: reads pipeline output, produces a high-level analysis,
and writes it to alertslog/sp500_ema200.txt.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import config


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _bucket_label(pct: float) -> str:
    apct = abs(pct)
    if apct <= 2:
        return "0-2%"
    if apct <= 5:
        return "2-5%"
    return "5-10%"


def _side(pct: float | None) -> str:
    if pct is None:
        return "unknown"
    return "above" if pct > 0 else "below" if pct < 0 else "at"


def analyse(output_dir: str | None = None) -> dict:
    out = Path(output_dir or config.OUTPUT_DIR)
    summary = load_json(out / "coworker_summary.json")
    if not summary:
        return {"error": "coworker_summary.json not found", "generated_at": _now()}

    metadata = summary.get("metadata", {})
    exec_summary = summary.get("executive_summary", {})
    all_ranked = summary.get("all_stocks_ranked", [])
    near_emas = summary.get("stocks_near_emas", [])
    top_emerging = summary.get("top_emerging_trends", [])
    sector_heatmap = summary.get("sector_heatmap", {})

    ema200_stocks = _extract_ema200_stocks(near_emas, all_ranked)

    sector_breakdown = defaultdict(list)
    distance_buckets = defaultdict(list)
    above_count = 0
    below_count = 0

    for s in ema200_stocks:
        dist = s.get("ema200_distance_pct")
        if dist is None:
            continue
        sector_breakdown[s.get("sector", "Unknown")].append(s)
        distance_buckets[_bucket_label(dist)].append(s["ticker"])
        if dist > 0:
            above_count += 1
        elif dist < 0:
            below_count += 1

    sector_summary = {}
    for sector, stocks in sorted(sector_breakdown.items(), key=lambda x: -len(x[1])):
        top = sorted(stocks, key=lambda x: x.get("trend_score", 0), reverse=True)[:5]
        sector_summary[sector] = {
            "count": len(stocks),
            "tickers": [
                {
                    "ticker": s["ticker"],
                    "price": s.get("price"),
                    "ema200_distance_pct": s.get("ema200_distance_pct"),
                    "side": _side(s.get("ema200_distance_pct")),
                    "trend_score": s.get("trend_score"),
                    "rsi": s.get("rsi"),
                }
                for s in top
            ],
        }

    top_bullish = sorted(
        [s for s in ema200_stocks if (s.get("ema200_distance_pct") or 0) > 0],
        key=lambda x: x.get("trend_score", 0),
        reverse=True,
    )[:10]

    top_bearish_recovery = sorted(
        [s for s in ema200_stocks if (s.get("ema200_distance_pct") or 0) < 0],
        key=lambda x: x.get("trend_score", 0),
        reverse=True,
    )[:10]

    return {
        "generated_at": _now(),
        "pipeline_generated_at": metadata.get("generated_at"),
        "total_sp500_analyzed": metadata.get("total_stocks_analyzed", 0),
        "ema200_band": f"0-{config.EMA200_NEAR_PCT_MAX}%",
        "overview": {
            "stocks_within_ema200_band": len(ema200_stocks),
            "above_ema200": above_count,
            "below_ema200": below_count,
            "stocks_near_all_emas": exec_summary.get("stocks_near_ema", 0),
            "top_emerging_count": exec_summary.get("top_emerging_count", 0),
        },
        "distance_distribution": {
            bucket: {"count": len(tickers), "tickers": tickers}
            for bucket, tickers in sorted(distance_buckets.items())
        },
        "sector_breakdown": sector_summary,
        "top_bullish_near_ema200": [
            _stock_brief(s) for s in top_bullish
        ],
        "top_bearish_recovery_candidates": [
            _stock_brief(s) for s in top_bearish_recovery
        ],
        "market_breadth": _market_breadth(all_ranked),
    }


def _extract_ema200_stocks(near_emas: list[dict], all_ranked: list[dict]) -> list[dict]:
    """Get all stocks within the configured EMA200 band from the best available source."""
    result = []
    for s in near_emas:
        dist = s.get("ema_proximity", {}).get("EMA200_pct_from_price")
        if dist is not None and abs(dist) <= config.EMA200_NEAR_PCT_MAX:
            entry = dict(s)
            entry["ema200_distance_pct"] = dist
            result.append(entry)

    seen = {s["ticker"] for s in result}
    for s in all_ranked:
        if s["ticker"] in seen:
            continue
        if s.get("ema_position") in ("near_ema200_daily",):
            result.append(s)

    return result


def _stock_brief(s: dict) -> dict:
    return {
        "ticker": s["ticker"],
        "company": s.get("company", ""),
        "sector": s.get("sector", ""),
        "price": s.get("price"),
        "ema200_distance_pct": s.get("ema200_distance_pct"),
        "side": _side(s.get("ema200_distance_pct")),
        "trend_score": s.get("trend_score"),
        "rsi": s.get("rsi"),
        "period_return": s.get("period_return"),
    }


def _market_breadth(all_ranked: list[dict]) -> dict:
    if not all_ranked:
        return {}
    scores = [s.get("trend_score", 0) for s in all_ranked]
    avg = round(sum(scores) / len(scores), 1)
    above_70 = sum(1 for sc in scores if sc >= 70)
    below_40 = sum(1 for sc in scores if sc < 40)
    return {
        "avg_trend_score": avg,
        "stocks_score_above_70": above_70,
        "stocks_score_below_40": below_40,
        "breadth_pct": round(above_70 / len(scores) * 100, 1),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_alert_text(analysis: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("SP500 EMA200 DAILY ALERT")
    lines.append(f"Generated: {analysis.get('generated_at', 'N/A')}")
    lines.append(f"Pipeline data from: {analysis.get('pipeline_generated_at', 'N/A')}")
    lines.append("=" * 70)

    if "error" in analysis:
        lines.append(f"\nERROR: {analysis['error']}")
        return "\n".join(lines)

    ov = analysis.get("overview", {})
    lines.append(f"\nTotal S&P 500 analyzed: {analysis.get('total_sp500_analyzed', 0)}")
    lines.append(f"EMA200 proximity band: +/- {analysis.get('ema200_band', 'N/A')}")
    lines.append(f"Stocks within EMA200 band: {ov.get('stocks_within_ema200_band', 0)}")
    lines.append(f"  Above EMA200: {ov.get('above_ema200', 0)}")
    lines.append(f"  Below EMA200: {ov.get('below_ema200', 0)}")
    lines.append(f"Stocks near any EMA: {ov.get('stocks_near_all_emas', 0)}")
    lines.append(f"Strong emerging trends (score>=70): {ov.get('top_emerging_count', 0)}")

    breadth = analysis.get("market_breadth", {})
    if breadth:
        lines.append(f"\n--- Market Breadth ---")
        lines.append(f"Avg trend score: {breadth.get('avg_trend_score', 'N/A')}")
        lines.append(f"Bullish (score>=70): {breadth.get('stocks_score_above_70', 0)} ({breadth.get('breadth_pct', 0)}%)")
        lines.append(f"Weak (score<40): {breadth.get('stocks_score_below_40', 0)}")

    dist = analysis.get("distance_distribution", {})
    if dist:
        lines.append(f"\n--- Distance Distribution ---")
        for bucket, data in dist.items():
            lines.append(f"  {bucket:>6s}: {data['count']:3d} stocks")

    lines.append(f"\n--- Top Bullish Near EMA200 ---")
    for s in analysis.get("top_bullish_near_ema200", []):
        lines.append(
            f"  {s['ticker']:6s} | {s.get('ema200_distance_pct', 0):+6.2f}% above | "
            f"Score: {s.get('trend_score', 0):5.1f} | RSI: {s.get('rsi', 'N/A'):>6} | "
            f"{s.get('sector', '')[:20]}"
        )

    lines.append(f"\n--- Top Bearish Recovery Candidates ---")
    for s in analysis.get("top_bearish_recovery_candidates", []):
        lines.append(
            f"  {s['ticker']:6s} | {s.get('ema200_distance_pct', 0):+6.2f}% below | "
            f"Score: {s.get('trend_score', 0):5.1f} | RSI: {s.get('rsi', 'N/A'):>6} | "
            f"{s.get('sector', '')[:20]}"
        )

    sectors = analysis.get("sector_breakdown", {})
    if sectors:
        lines.append(f"\n--- Sector Breakdown (stocks near EMA200) ---")
        for sector, data in sectors.items():
            tickers_str = ", ".join(t["ticker"] for t in data["tickers"][:5])
            lines.append(f"  {sector[:25]:25s} ({data['count']:2d}): {tickers_str}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def run(output_dir: str | None = None, alerts_dir: str | None = None):
    out = Path(output_dir or config.OUTPUT_DIR)
    alerts = Path(alerts_dir or config.ALERTS_DIR)
    alerts.mkdir(parents=True, exist_ok=True)

    analysis = analyse(output_dir)

    analysis_path = alerts / "sp500_ema200_analysis.json"
    with open(analysis_path, "w") as f:
        json.dump(analysis, f, indent=2)

    alert_path = alerts / "sp500_ema200.txt"
    with open(alert_path, "w") as f:
        f.write(format_alert_text(analysis))

    print(f"EMA200 daily alert written to {alert_path}")
    print(f"JSON analysis written to {analysis_path}")
    return analysis


if __name__ == "__main__":
    run()
