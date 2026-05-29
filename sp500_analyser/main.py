#!/usr/bin/env python3
"""
SP500 Coworker Pipeline
=======================
Fetches SP500 stock data from Polygon (OHLCV) and Finviz (fundamentals/technicals/EMAs),
analyzes for emerging trends and EMA proximity, and outputs coworker-friendly JSON.

Usage:
    python main.py                    # Full run (all ~503 tickers)
    python main.py --limit 50         # Test with first 50 tickers
    python main.py --tickers AAPL,MSFT,GOOGL  # Specific tickers only
    python main.py --skip-polygon     # Skip Polygon, use cached data
    python main.py --skip-finviz      # Skip Finviz, use cached data
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .sp500_tickers import get_sp500_tickers
from .polygon_fetcher import fetch_all_tickers, save_polygon_data
from .finviz_fetcher import fetch_all_finviz, save_finviz_data
from .analyzer import analyze_all, generate_coworker_summary, save_analysis


def load_cached(filename: str) -> list[dict]:
    path = Path(config.OUTPUT_DIR) / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def write_cowork_pipeline_ready(output_dir: str, summary: dict) -> None:
    """Signal host tooling (e.g. Cursor agent LaunchAgent) that fresh coworker JSON is available."""
    out = Path(output_dir)
    marker = out / ".cowork_pipeline_ready.json"
    payload = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total_stocks_analyzed": summary.get("metadata", {}).get("total_stocks_analyzed"),
        "coworker_summary_file": "coworker_summary.json",
    }
    marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nCowork hook: wrote {marker}")


def main():
    parser = argparse.ArgumentParser(description="SP500 Coworker Data Pipeline")
    parser.add_argument("--limit", type=int, help="Limit number of tickers to process")
    parser.add_argument("--tickers", type=str, help="Comma-separated list of specific tickers")
    parser.add_argument("--skip-polygon", action="store_true", help="Skip Polygon fetch, use cached data")
    parser.add_argument("--skip-finviz", action="store_true", help="Skip Finviz fetch, use cached data")
    parser.add_argument("--output-dir", type=str, default=config.OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    config.OUTPUT_DIR = args.output_dir

    if not config.POLYGON_API_KEY and not args.skip_polygon:
        print("ERROR: POLYGON_API_KEY not set. Add it to .env file or set environment variable.")
        print("Get a free key at https://polygon.io/")
        sys.exit(1)

    print("=" * 60)
    print("SP500 COWORKER DATA PIPELINE")
    print("=" * 60)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
        print(f"\nUsing {len(tickers)} specified tickers: {tickers}")
    else:
        print("\nFetching SP500 ticker list from Wikipedia...")
        tickers = get_sp500_tickers()
        print(f"Found {len(tickers)} SP500 tickers")

    if args.limit:
        tickers = tickers[:args.limit]
        print(f"Limited to first {args.limit} tickers")

    print(
        f"\n--- Step 1: Polygon Daily Bars "
        f"(~{config.POLYGON_EMA200_LOOKBACK_DAYS}d for EMA{config.POLYGON_EMA200_PERIOD}, "
        f"last {config.LOOKBACK_DAYS}d for trend) ---"
    )
    if args.skip_polygon:
        print("Skipping Polygon fetch, loading cached data...")
        polygon_data = load_cached("polygon_daily_bars.json")
        print(f"Loaded {len(polygon_data)} tickers from cache")
        if polygon_data:
            bar_count = len(polygon_data[0].get("results", []))
            if bar_count < config.POLYGON_EMA200_PERIOD:
                print(
                    f"WARNING: cache has ~{bar_count} bars per ticker; need "
                    f"{config.POLYGON_EMA200_PERIOD}+ for Polygon EMA200. "
                    "Re-run without --skip-polygon to refresh."
                )
    else:
        polygon_data = fetch_all_tickers(tickers)
        save_polygon_data(polygon_data, args.output_dir)

    print(f"\n--- Step 2: Finviz Fundamentals & Technicals ---")
    if args.skip_finviz:
        print("Skipping Finviz fetch, loading cached data...")
        finviz_data = load_cached("finviz_metrics.json")
        print(f"Loaded {len(finviz_data)} tickers from cache")
    else:
        finviz_data = fetch_all_finviz(tickers)
        save_finviz_data(finviz_data, args.output_dir)

    print(f"\n--- Step 3: Analysis & Trend Detection ---")
    analyzed = analyze_all(polygon_data, finviz_data)
    summary = generate_coworker_summary(analyzed)
    save_analysis(analyzed, summary, args.output_dir)

    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"\nTotal stocks analyzed: {summary['metadata']['total_stocks_analyzed']}")
    ema_meta = summary.get("metadata", {}).get("ema200_computation", {})
    if ema_meta:
        print(
            f"EMA200 from Polygon: {ema_meta.get('tickers_with_polygon_ema200', 0)} tickers "
            f"(Finviz fallback: {ema_meta.get('tickers_with_finviz_fallback', 0)})"
        )
    print(
        f"Stocks near daily EMA200 "
        f"({config.EMA200_NEAR_PCT_MIN}%–{config.EMA200_NEAR_PCT_MAX}%): "
        f"{summary['executive_summary']['stocks_near_ema200_daily']}"
    )
    print(f"Stocks near EMAs (all): {summary['executive_summary']['stocks_near_ema']}")
    print(f"Top emerging trends: {summary['executive_summary']['top_emerging_count']}")

    print(f"\nOutput files in '{args.output_dir}/':")
    print(f"  - polygon_daily_bars.json   (raw OHLCV data)")
    print(f"  - finviz_metrics.json       (fundamentals + technicals + EMAs)")
    print(f"  - full_analysis.json        (all stocks with scores)")
    print(f"  - coworker_summary.json     (structured summary for coworker)")
    print(f"  - stocks_near_ema200_daily.json (price within EMA200 % band)")

    near200 = summary.get("stocks_near_ema200_daily") or []
    if near200:
        print(f"\n--- Stocks within {config.EMA200_NEAR_PCT_MIN}%–{config.EMA200_NEAR_PCT_MAX}% of daily EMA200 ({len(near200)}) ---")
        for s in near200[:25]:
            dist = s.get("ema200_distance_pct")
            dist_s = f"{dist:+.2f}%" if dist is not None else "N/A"
            print(
                f"  {s['ticker']:6s} | {dist_s:>8s} from EMA200 | "
                f"{s.get('side_of_ema200', ''):5s} | {s.get('sector', '')[:18]}"
            )
        if len(near200) > 25:
            print(f"  ... and {len(near200) - 25} more (see stocks_near_ema200_daily.json)")

    if summary.get("stocks_near_emas"):
        print(f"\n--- Top 10 Stocks Near EMAs ---")
        near = sorted(summary["stocks_near_emas"], key=lambda x: x["trend_score"], reverse=True)[:10]
        for s in near:
            print(f"  {s['ticker']:6s} | Score: {s['trend_score']:5.1f} | {s['ema_position']:30s} | RSI: {s.get('rsi', 'N/A')}")

    if summary.get("top_emerging_trends"):
        print(f"\n--- Top 10 Emerging Trends ---")
        for s in summary["top_emerging_trends"][:10]:
            ret = s['trend'].get('period_return_pct', 'N/A')
            print(f"  {s['ticker']:6s} | Score: {s['trend_score']:5.1f} | {s['sector']:20s} | Return: {ret}%")

    if config.WRITE_COWORK_READY:
        write_cowork_pipeline_ready(args.output_dir, summary)


if __name__ == "__main__":
    main()
