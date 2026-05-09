"""Fetch the current S&P 500 ticker list from Wikipedia."""
from __future__ import annotations

import pandas as pd
import requests
from io import StringIO


def get_sp500_tickers() -> list[str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    tickers = df["Symbol"].tolist()
    tickers = [t.replace(".", "-") for t in tickers]
    return sorted(tickers)


if __name__ == "__main__":
    tickers = get_sp500_tickers()
    print(f"Found {len(tickers)} S&P 500 tickers")
    print(tickers[:10])
