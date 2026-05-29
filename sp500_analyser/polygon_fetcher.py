"""Fetch daily OHLCV data from Polygon.io for the last N days."""
from __future__ import annotations

import time
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests
from tqdm import tqdm

from . import config


def fetch_daily_bars(ticker: str, from_date: str, to_date: str) -> dict | None:
    url = (
        f"{config.POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}"
        f"/range/1/day/{from_date}/{to_date}"
    )
    params = {
        "adjusted": "true",
        "sort": "asc",
        "apiKey": config.POLYGON_API_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            print(f"  Rate limited on {ticker}, waiting 60s...")
            time.sleep(60)
            resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("resultsCount", 0) == 0:
            return None
        return {
            "ticker": ticker,
            "results": [
                {
                    "date": datetime.fromtimestamp(r["t"] / 1000).strftime("%Y-%m-%d"),
                    "open": r["o"],
                    "high": r["h"],
                    "low": r["l"],
                    "close": r["c"],
                    "volume": r["v"],
                    "vwap": r.get("vw"),
                    "num_transactions": r.get("n"),
                }
                for r in data["results"]
            ],
        }
    except requests.RequestException as e:
        print(f"  Error fetching {ticker}: {e}")
        return None


def fetch_all_tickers(tickers: list[str], days: int = None) -> list[dict]:
    if days is None:
        days = max(config.LOOKBACK_DAYS, config.POLYGON_EMA200_LOOKBACK_DAYS)
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")

    results = []
    print(
        f"Fetching Polygon data for {len(tickers)} tickers ({from_date} to {to_date}, "
        f"~{days}d calendar for EMA{config.POLYGON_EMA200_PERIOD} + {config.LOOKBACK_DAYS}d trend)..."
    )

    for i, ticker in enumerate(tqdm(tickers, desc="Polygon")):
        data = fetch_daily_bars(ticker, from_date, to_date)
        if data:
            results.append(data)
        if i < len(tickers) - 1:
            time.sleep(config.POLYGON_DELAY)

    return results


def save_polygon_data(data: list[dict], output_dir: str = None):
    if output_dir is None:
        output_dir = config.OUTPUT_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / "polygon_daily_bars.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved Polygon data for {len(data)} tickers to {path}")
    return path


if __name__ == "__main__":
    from sp500_analyser.sp500_tickers import get_sp500_tickers

    tickers = get_sp500_tickers()[:5]
    data = fetch_all_tickers(tickers)
    save_polygon_data(data)
