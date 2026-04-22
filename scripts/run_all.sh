#!/usr/bin/env bash
# Orchestrator. Run from project root:
#   ./scripts/run_all.sh              # full run
#   ./scripts/run_all.sh --quick      # small example count
#   ./scripts/run_all.sh --gateway    # only gateway suite
#   ./scripts/run_all.sh --data       # only orderbook history suite
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

mkdir -p results

QUICK=0
ONLY=""
for arg in "$@"; do
  case "$arg" in
    --quick)    QUICK=1 ;;
    --gateway)  ONLY="gateway" ;;
    --data)     ONLY="data" ;;
    --help|-h)  sed -n '2,10p' "$0"; exit 0 ;;
  esac
done

if [[ "$QUICK" == "1" ]]; then
  export FUZZ_MAX_EXAMPLES="${FUZZ_MAX_EXAMPLES:-20}"
  CLI_MAX="--max-examples 20"
else
  export FUZZ_MAX_EXAMPLES="${FUZZ_MAX_EXAMPLES:-75}"
  CLI_MAX="--max-examples 75"
fi

echo "================================================================"
echo " Graylayer Fuzz — settings"
echo "   FUZZ_MAX_EXAMPLES = $FUZZ_MAX_EXAMPLES"
echo "   FUZZ_RATE_LIMIT_SLEEP = ${FUZZ_RATE_LIMIT_SLEEP:-0.25}"
echo "   ONLY = ${ONLY:-<all>}"
echo "================================================================"

# ── 1. Schemathesis CLI against each spec (safe mode: GET only) ──
#    We also run it via pytest below to collect rich findings; the CLI
#    run produces a compact terminal report we redirect to results/.
run_cli_gateway() {
  echo ">> schemathesis CLI → gateway spec"
  schemathesis run specs/market_proxy.yaml \
    --url "${GRAYLAYER_GATEWAY_URL:-http://gateway.graylayer.tech}" \
    --header "X-API-Key:${GRAYLAYER_GATEWAY_API_KEY:-}" \
    --checks all \
    --include-method GET \
    $CLI_MAX \
    --report-preserve-bytes \
    > results/schemathesis_gateway.txt 2>&1 || true
}

run_cli_data() {
  echo ">> schemathesis CLI → data spec"
  schemathesis run specs/orderbook_history.yaml \
    --url "${GRAYLAYER_DATA_URL:-http://data.graylayer.tech}" \
    --header "x-api-key:${GRAYLAYER_DATA_API_KEY:-}" \
    --checks all \
    --include-method GET \
    $CLI_MAX \
    --report-preserve-bytes \
    > results/schemathesis_data.txt 2>&1 || true
}

if [[ "$ONLY" == "" || "$ONLY" == "gateway" ]]; then run_cli_gateway; fi
if [[ "$ONLY" == "" || "$ONLY" == "data" ]];    then run_cli_data;    fi

# ── 2. pytest: rich fuzz + negative + differential + stateful suites ──
echo ">> pytest suite"
PYTEST_ARGS=(-q -ra)
if [[ "$ONLY" == "gateway" ]]; then PYTEST_ARGS+=( -m "gateway or negative or differential or stateful" ); fi
if [[ "$ONLY" == "data" ]];    then PYTEST_ARGS+=( -m "data or negative or differential or stateful" ); fi

# Don't let test failures abort the script — we *want* failures in the reports.
pytest "${PYTEST_ARGS[@]}" || true

# ── 3. Summary + plots ──
echo ">> summarize"
python scripts/summarize.py

echo ""
echo "Done. Artifacts in results/:"
ls -la results/ | sed 's/^/    /'
