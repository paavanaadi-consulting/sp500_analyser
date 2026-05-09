#!/bin/bash
# Run SP500 pipeline and push output to repo for the remote analyst agent.
# Schedule this locally (e.g., cron) to run before the remote routine fires.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== SP500 Pipeline: $(date) ==="

# Run the pipeline, storing output inside the repo for git tracking
python3 main.py --output-dir "$SCRIPT_DIR/data"

# Commit and push the fresh data
git add data/
git commit -m "data: update SP500 analysis $(date +%Y-%m-%d)" || echo "No changes to commit"
git push origin main
echo "=== Done ==="
