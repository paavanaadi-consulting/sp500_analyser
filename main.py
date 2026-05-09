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
from pathlib import Path

import config
from sp500_tickers import get_sp500_tickers
from polygon_fetcher import fetch_all_tickers, save_polygon_data
from finviz_fetcher import fetch_all_finviz, save_finviz_data
from analyzer import analyze_all, generate_coworker_summary, save_analysis


def load_cached(filename: str) -> list[dict]:
    path = Path(config.OUTPUT_DIR) / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


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

    print(f"\n--- Step 1: Polygon Daily Bars (last {config.LOOKBACK_DAYS} days) ---")
    if args.skip_polygon:
        print("Skipping Polygon fetch, loading cached data...")
        polygon_data = load_cached("polygon_daily_bars.json")
        print(f"Loaded {len(polygon_data)} tickers from cache")
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
    print(f"Stocks near EMAs: {summary['executive_summary']['stocks_near_ema']}")
    print(f"Top emerging trends: {summary['executive_summary']['top_emerging_count']}")

    print(f"\nOutput files in '{args.output_dir}/':")
    print(f"  - polygon_daily_bars.json   (raw OHLCV data)")
    print(f"  - finviz_metrics.json       (fundamentals + technicals + EMAs)")
    print(f"  - full_analysis.json        (all stocks with scores)")
    print(f"  - coworker_summary.json     (structured summary for coworker)")

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


if __name__ == "__main__":
    main()
