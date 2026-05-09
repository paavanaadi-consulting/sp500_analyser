# SP500 Coworker Pipeline

Fetches SP500 stock data from **Polygon.io** (daily OHLCV) and **Finviz** (fundamentals, technicals, EMAs), analyzes for emerging trends and EMA proximity, and outputs structured JSON for a coworker agent to derive insights.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Polygon API key (free at https://polygon.io/)
```

## Usage

```bash
# Full run (all ~503 SP500 tickers — takes a while due to API rate limits)
python main.py

# Test with a few tickers
python main.py --limit 10
python main.py --tickers AAPL,MSFT,GOOGL,NVDA

# Skip data sources if already cached
python main.py --skip-polygon
python main.py --skip-finviz
```

## Output Files

By default, outputs go to a sibling folder outside this repo: `../sp500_output/`.
You can override this with `--output-dir`.

| File | Description |
|------|-------------|
| `polygon_daily_bars.json` | Raw OHLCV data per ticker (last 10 days) |
| `finviz_metrics.json` | Fundamentals, technicals, EMAs per ticker |
| `full_analysis.json` | Complete analysis with trend scores |
| `coworker_summary.json` | Structured summary for coworker consumption |

## Coworker Summary Structure

The `coworker_summary.json` is designed for easy consumption:

- **`stocks_near_emas`** — Stocks near EMA20/50/200 (potential inflection points)
- **`top_emerging_trends`** — Highest-scoring stocks with full data attached
- **`sector_heatmap`** — Sector-level aggregation with top tickers per sector
- **`all_stocks_ranked`** — Every stock ranked by emerging trend score

## Emerging Trend Score (0-100)

Factors: EMA proximity, 10-day price return, consecutive up days, volume trend, RSI position.
