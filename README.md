# SP500 Coworker Pipeline

Fetches SP500 stock data from **Polygon.io** (daily OHLCV) and **Finviz** (fundamentals, technicals, EMAs), analyzes for emerging trends and EMA proximity, and outputs structured JSON for a coworker agent to derive insights.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Polygon API key (free at https://polygon.io/)
```

## Docker (Docker Desktop) — daily schedule

The repo includes a `Dockerfile` and `docker-compose.yml` that run the pipeline **Monday–Friday at 7:00 US Eastern** (`America/New_York`, which follows EST/EDT), using [Ofelia](https://github.com/mcuadros/ofelia) with **`job-exec`** into a long-lived container (same bind-mounted output directory on your Mac).

1. Install and start **Docker Desktop**.
2. In this directory, copy `.env.example` → `.env` and set at least **`POLYGON_API_KEY`**. Optionally set **`SP500_HOST_DATA_DIR`** to an **absolute** path for outputs (defaults to **`../sp500_output`** next to this repo, same as local `python main.py`).
3. Start the stack (builds the image, starts the scheduler, and keeps **sp500_pipeline_jobspec** running for Ofelia):

   ```bash
   docker compose up -d --build
   ```

4. **Outputs** (including `coworker_summary.json`) land on the host at **`SP500_HOST_DATA_DIR`** (default `../sp500_output`). After each successful scheduled or manual run in Docker, **`SP500_WRITE_COWORK_READY`** is on, so the pipeline also writes **`.cowork_pipeline_ready.json`** there for local automation.

5. **Run once manually** (same bind mount and cowork marker):

   ```bash
   docker compose run --rm pipeline-jobspec python main.py --output-dir /data
   ```

### Cursor “cowork” agent on your Mac (after each run)

The [Cursor Agent CLI](https://cursor.com/docs/cli/using) (`agent` on your `PATH`) can read the fresh summary on disk.

- **Manual:** from the repo, `chmod +x scripts/trigger-cursor-cowork-agent.sh` once, then:

  ```bash
  ./scripts/trigger-cursor-cowork-agent.sh
  ```

  The script uses **`SP500_COWORK_AGENT_WORKSPACE`** from `.env` if set (otherwise the parent `tradingproject` folder), runs `agent --workspace … --mode ask --print` with a prompt grounded in **`coworker_summary.json`**, and falls back to **`open -a Cursor`** if `agent` is not installed.

- **Automatic when the marker updates (macOS):** install **`scripts/com.sp500-analyser.cowork-ready.plist.example`** into `~/Library/LaunchAgents/` (edit paths so **WatchPaths** points at your real **`…/sp500_output/.cowork_pipeline_ready.json`**), then `launchctl load …`. Each pipeline completion touches that file and launchd can run the script above.

To run the cowork hook from **local Python** (not Docker), set **`SP500_WRITE_COWORK_READY=1`** in `.env` before `python main.py`.

### Stop scheduling

```bash
docker compose stop
```

Containers stay on disk with **`restart: always`**, so they come back when Docker starts again. To remove them entirely, use **`docker compose down`** — then run **`docker compose up -d`** again (or use the Docker-socket LaunchAgent below) before the weekday job runs.

### After Docker Desktop restarts

Compose uses **`restart: always`** on both services. When the Docker engine comes back (Docker Desktop reopened, sleep/wake, reboot), Docker should start **ofelia** and **pipeline-jobspec** again automatically, as long as those containers still exist (that is, you did not run `docker compose down`).

In Docker Desktop, turn on **Settings → General → “Start Docker Desktop when you sign in”** so the engine is available without a manual open.

**Optional (macOS):** If you want the stack to come up whenever the Docker socket appears (or on login), install the LaunchAgent:

1. `chmod +x scripts/docker-compose-up-when-ready.sh`
2. Copy `scripts/com.sp500-analyser.docker.plist.example` to `~/Library/LaunchAgents/com.sp500-analyser.docker.plist`, edit `YOUR_USERNAME` and paths, then `launchctl load ~/Library/LaunchAgents/com.sp500-analyser.docker.plist`

Ofelia logs: `docker compose logs -f ofelia`. Leave Docker Desktop running overnight so the weekday 7 AM job can fire.

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
