import os
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
POLYGON_BASE_URL = "https://api.polygon.io"

FINVIZ_API_KEY = os.getenv("FINVIZ_API_KEY", "")
FINVIZ_ELITE_BASE = "https://elite.finviz.com"

LOOKBACK_DAYS = 10

OUTPUT_DIR = "output"

# Polygon free tier: 5 calls/min
POLYGON_DELAY = 12.5
# Finviz pagination delay
FINVIZ_DELAY = 0.5
