import random
import pytest


@pytest.fixture
def sample_finviz_entry():
    return {
        "ticker": "AAPL",
        "Company": "Apple Inc.",
        "Sector": "Technology",
        "Industry": "Consumer Electronics",
        "Price": "185.50",
        "Market Cap": "2.9T",
        "P/E": "30.25",
        "Forward P/E": "28.10",
        "PEG": "2.15",
        "EPS (ttm)": "6.13",
        "EPS next Y": "7.20",
        "ROE": "171.00%",
        "Profit Margin": "25.30%",
        "Debt/Eq": "1.80",
        "RSI (14)": "55.00",
        "SMA20": "2.50%",
        "SMA50": "5.00%",
        "SMA200": "10.00%",
        "EMA20": "1.80%",
        "EMA50": "4.20%",
        "EMA200": "8.50%",
        "Beta": "1.25",
        "Recom": "1.80",
        "Target Price": "200.00",
        "Perf Week": "1.50%",
        "Perf Month": "3.20%",
        "Perf Quarter": "-2.10%",
        "Perf YTD": "15.00%",
        "Change": "0.75%",
    }


@pytest.fixture
def sample_polygon_entry():
    rng = random.Random(42)
    base_price = 180.0
    bars = []
    for i in range(220):
        close = base_price + rng.uniform(-5, 5) + (i * 0.02)
        bars.append({
            "date": f"2025-{(i // 30) + 1:02d}-{(i % 28) + 1:02d}",
            "open": close - rng.uniform(0, 2),
            "high": close + rng.uniform(0, 3),
            "low": close - rng.uniform(0, 3),
            "close": close,
            "volume": rng.randint(50_000_000, 100_000_000),
        })
    return {"ticker": "AAPL", "results": bars}


@pytest.fixture
def sample_polygon_entry_short():
    return {
        "ticker": "AAPL",
        "results": [
            {
                "date": f"2025-01-{i + 1:02d}",
                "open": 180 + i,
                "high": 182 + i,
                "low": 179 + i,
                "close": 181 + i,
                "volume": 50_000_000,
            }
            for i in range(10)
        ],
    }
