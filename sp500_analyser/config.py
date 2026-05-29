import os
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
POLYGON_BASE_URL = "https://api.polygon.io"

FINVIZ_API_KEY = os.getenv("FINVIZ_API_KEY", "")
FINVIZ_ELITE_BASE = "https://elite.finviz.com"

LOOKBACK_DAYS = 10

# Daily bars for EMA200: ~200 trading sessions need ~280–320 calendar days of history.
POLYGON_EMA200_PERIOD = int(os.getenv("POLYGON_EMA200_PERIOD", "200"))
POLYGON_EMA200_LOOKBACK_DAYS = int(os.getenv("POLYGON_EMA200_LOOKBACK_DAYS", "320"))

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(_PACKAGE_DIR)
_TRADING_DIR = os.path.dirname(PROJECT_DIR)
OUTPUT_DIR = os.path.join(_TRADING_DIR, "sp500_output")
ALERTS_DIR = os.getenv("SP500_ALERTS_DIR", os.path.join(_TRADING_DIR, "alertslog"))

# Polygon API delay (seconds between requests)
POLYGON_DELAY = 0.2
# Finviz pagination delay
FINVIZ_DELAY = 0.5

# When true, main.py writes .cowork_pipeline_ready.json after a successful run (for local Cursor agent hooks).
WRITE_COWORK_READY = os.getenv("SP500_WRITE_COWORK_READY", "").lower() in ("1", "true", "yes")

EMA200_NEAR_PCT_MIN = float(os.getenv("EMA200_NEAR_PCT_MIN", "0"))
EMA200_NEAR_PCT_MAX = float(os.getenv("EMA200_NEAR_PCT_MAX", "10"))
