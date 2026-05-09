#!/usr/bin/env bash
# Run Cursor Agent (Claude or your default model) against fresh coworker_summary.json.
# Intended after the Docker pipeline writes .cowork_pipeline_ready.json on the host
# (LaunchAgent WatchPaths → this script).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi

DATA_DIR="${SP500_HOST_DATA_DIR:-}"
if [[ -z "$DATA_DIR" ]]; then
  DATA_DIR="$(cd "$ROOT/.." && pwd)/sp500_output"
fi
DATA_DIR="$(cd "$DATA_DIR" && pwd)"

WS="${SP500_COWORK_AGENT_WORKSPACE:-$(cd "$ROOT/.." && pwd)}"
SUMMARY="$DATA_DIR/coworker_summary.json"
READY="$DATA_DIR/.cowork_pipeline_ready.json"

if [[ ! -f "$SUMMARY" ]]; then
  echo "trigger-cursor-cowork-agent: missing $SUMMARY" >&2
  exit 1
fi

PROMPT="The SP500 pipeline just finished (metadata: $READY). Read and analyze the JSON at this absolute path: $SUMMARY

You are my equity cowork agent for idea generation only (not personalized investment advice). From the data, give: (1) a short executive summary, (2) sector highlights, (3) notable emerging trends and EMA proximity names, (4) open questions or data gaps. Keep it concise."

if command -v agent >/dev/null 2>&1; then
  exec agent --workspace "$WS" --mode ask --print --output-format text "$PROMPT"
fi

echo "trigger-cursor-cowork-agent: 'agent' CLI not on PATH. Open Cursor docs: https://cursor.com/docs/cli/using — opening Cursor on workspace as fallback." >&2
open -a "Cursor" "$WS" || true
