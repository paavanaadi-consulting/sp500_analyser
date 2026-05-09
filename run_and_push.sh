#!/bin/bash
# Run SP500 pipeline and write output outside this repository.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
OUT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/sp500_output"

echo "=== SP500 Pipeline: $(date) ==="

# Run the pipeline, storing output outside this repo
python3 main.py --output-dir "$OUT_DIR"

echo "Output written to: $OUT_DIR"
echo "=== Done ==="
