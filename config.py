import os
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
POLYGON_BASE_URL = "https://api.polygon.io"

FINVIZ_API_KEY = os.getenv("FINVIZ_API_KEY", "")
FINVIZ_ELITE_BASE = "https://elite.finviz.com"

LOOKBACK_DAYS = 10

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "sp500_output")

# Polygon API delay (seconds between requests)
POLYGON_DELAY = 0.2
# Finviz pagination delay
FINVIZ_DELAY = 0.5

# When true, main.py writes .cowork_pipeline_ready.json after a successful run (for local Cursor agent hooks).
WRITE_COWORK_READY = os.getenv("SP500_WRITE_COWORK_READY", "").lower() in ("1", "true", "yes")
