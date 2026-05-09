"""
Fetch all SP500 metrics from Finviz Elite screener using API key.
Uses the bulk screener/export endpoint instead of individual ticker lookups.

Source URL pattern:
  https://elite.finviz.com/screener?v=151&f=idx_sp500&ft=4&o=open
  https://elite.finviz.com/export.ashx?v=152&f=idx_sp500&ft=4&auth=API_KEY
"""
from __future__ import annotations

import time
import json
import csv
from io import StringIO
from pathlib import Path

import requests
import pandas as pd
from tqdm import tqdm

import config

SCREENER_VIEWS = {
    "overview": 111,
    "valuation": 121,
    "financial": 161,
    "ownership": 131,
    "performance": 141,
    "technical": 171,
    "custom": 152,
}


def _build_screener_url(view: int = 152, export: bool = False) -> str:
    if export:
        return (
            f"{config.FINVIZ_ELITE_BASE}/export.ashx"
            f"?v={view}&f=idx_sp500&ft=4&auth={config.FINVIZ_API_KEY}"
        )
    return (
        f"{config.FINVIZ_ELITE_BASE}/screener.ashx"
        f"?v={view}&f=idx_sp500&ft=4&auth={config.FINVIZ_API_KEY}"
    )


def _request_headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def fetch_via_export(view: int = 152) -> pd.DataFrame | None:
    """Fetch all SP500 data via CSV export endpoint (fastest method)."""
    url = _build_screener_url(view=view, export=True)
    print(f"  Trying CSV export (view={view})...")
    try:
        resp = requests.get(url, headers=_request_headers(), timeout=60)
        resp.raise_for_status()
        if "text/csv" in resp.headers.get("Content-Type", "") or resp.text.strip().startswith('"'):
            df = pd.read_csv(StringIO(resp.text))
            print(f"  Export returned {len(df)} rows, {len(df.columns)} columns")
            return df
        else:
            print(f"  Export didn't return CSV, falling back to screener scrape...")
            return None
    except Exception as e:
        print(f"  Export failed: {e}")
        return None


def fetch_via_screener(view: int = 152) -> pd.DataFrame | None:
    """Fetch SP500 data by paginating through the screener HTML tables."""
    all_rows = []
    columns = None
    page = 1
    row_start = 1

    print(f"  Scraping screener pages (view={view})...")

    while True:
        url = (
            f"{config.FINVIZ_ELITE_BASE}/screener.ashx"
            f"?v={view}&f=idx_sp500&ft=4&r={row_start}&auth={config.FINVIZ_API_KEY}"
        )
        try:
            resp = requests.get(url, headers=_request_headers(), timeout=30)
            resp.raise_for_status()

            tables = pd.read_html(StringIO(resp.text))
            data_table = None
            for t in tables:
                if len(t) > 5 and "Ticker" in t.columns or (len(t.columns) > 5 and t.iloc[0].astype(str).str.contains("Ticker").any()):
                    data_table = t
                    break

            if data_table is None:
                for t in tables:
                    if len(t) > 5 and len(t.columns) > 5:
                        data_table = t
                        break

            if data_table is None or len(data_table) == 0:
                break

            if "Ticker" not in data_table.columns and len(data_table) > 0:
                data_table.columns = data_table.iloc[0]
                data_table = data_table.iloc[1:]

            if columns is None:
                columns = list(data_table.columns)

            all_rows.append(data_table)
            fetched = len(data_table)
            print(f"    Page {page}: {fetched} rows (total so far: {sum(len(r) for r in all_rows)})")

            if fetched < 20:
                break

            row_start += 20
            page += 1
            time.sleep(config.FINVIZ_DELAY)

        except Exception as e:
            print(f"    Error on page {page}: {e}")
            break

    if all_rows:
        df = pd.concat(all_rows, ignore_index=True)
        print(f"  Scraped {len(df)} total rows from {page} pages")
        return df
    return None


def fetch_multiple_views() -> pd.DataFrame:
    """Fetch data from multiple screener views and merge for complete coverage."""
    views_to_fetch = [
        ("custom", 152),
        ("valuation", 121),
        ("financial", 161),
        ("performance", 141),
        ("technical", 171),
    ]

    merged = None

    for view_name, view_id in views_to_fetch:
        print(f"\n  Fetching '{view_name}' view (v={view_id})...")

        df = fetch_via_export(view=view_id)
        if df is None:
            df = fetch_via_screener(view=view_id)

        if df is None or len(df) == 0:
            print(f"  Skipping '{view_name}' — no data returned")
            continue

        if "No." in df.columns:
            df = df.drop(columns=["No."], errors="ignore")

        if merged is None:
            merged = df
        else:
            overlap_cols = [c for c in df.columns if c in merged.columns and c != "Ticker"]
            new_cols = [c for c in df.columns if c not in merged.columns]
            if new_cols:
                merge_cols = ["Ticker"] + new_cols
                merged = merged.merge(df[merge_cols], on="Ticker", how="left")
                print(f"  Merged {len(new_cols)} new columns from '{view_name}'")
            else:
                print(f"  No new columns from '{view_name}', skipping merge")

        time.sleep(config.FINVIZ_DELAY)

    return merged


def fetch_all_finviz(tickers: list[str] = None) -> list[dict]:
    """
    Fetch all SP500 data from Finviz Elite screener.
    If tickers is provided, filters results to only those tickers.
    """
    if not config.FINVIZ_API_KEY:
        print("WARNING: FINVIZ_API_KEY not set. Falling back to individual ticker scraping.")
        return _fallback_individual_fetch(tickers or [])

    print(f"Fetching Finviz Elite screener data (all SP500)...")

    df = fetch_via_export(view=152)
    if df is None:
        df = fetch_multiple_views()

    if df is None or len(df) == 0:
        print("ERROR: Could not fetch Finviz data via any method.")
        return []

    if "Ticker" not in df.columns:
        for col in df.columns:
            if df[col].astype(str).str.match(r'^[A-Z]{1,5}$').mean() > 0.5:
                df = df.rename(columns={col: "Ticker"})
                break

    if tickers:
        ticker_set = set(t.upper() for t in tickers)
        df = df[df["Ticker"].isin(ticker_set)]
        print(f"Filtered to {len(df)} tickers from provided list")

    records = df.to_dict(orient="records")
    result = []
    for row in records:
        entry = {"ticker": row.get("Ticker", "")}
        for key, val in row.items():
            if key != "Ticker":
                entry[key] = val if pd.notna(val) else None
        result.append(entry)

    print(f"Finviz data ready: {len(result)} tickers, {len(df.columns)} metrics each")
    return result


def _fallback_individual_fetch(tickers: list[str]) -> list[dict]:
    """Fallback: fetch individual tickers via finvizfinance package."""
    from finvizfinance.quote import finvizfinance as fvf

    results = []
    print(f"Fetching Finviz metrics individually for {len(tickers)} tickers...")

    for i, ticker in enumerate(tqdm(tickers, desc="Finviz")):
        try:
            stock = fvf(ticker)
            fundament = stock.ticker_fundament()
            entry = {"ticker": ticker}
            entry.update(fundament)
            results.append(entry)
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
        if i < len(tickers) - 1:
            time.sleep(1.0)

    return results


def save_finviz_data(data: list[dict], output_dir: str = None):
    if output_dir is None:
        output_dir = config.OUTPUT_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / "finviz_metrics.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved Finviz data for {len(data)} tickers to {path}")
    return path


if __name__ == "__main__":
    data = fetch_all_finviz()
    if data:
        save_finviz_data(data)
        print(f"\nSample columns: {list(data[0].keys())[:20]}")
