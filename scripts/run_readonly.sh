#!/usr/bin/env bash
# Runs only read-only (GET) endpoints against the live Graylayer API.
# Results are saved to results/ as a timestamped JSON file.
# Usage: bash scripts/run_readonly.sh

set -euo pipefail

if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

BASE_URL="${GRAYLAYER_BASE_URL:-http://gateway.graylayer.tech/api/v1}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="results/run_${TIMESTAMP}.json"

echo "Target:  $BASE_URL"
echo "Results: $RESULT_FILE"
echo ""

pytest tests/ -m readonly -q \
  --json-report \
  --json-report-file="$RESULT_FILE"

echo ""
echo "Done. Results saved to $RESULT_FILE"
