#!/usr/bin/env bash
# Orchestrator. Run from project root:
#   ./scripts/run_all.sh              # full run
#   ./scripts/run_all.sh --quick      # small example count
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

mkdir -p results

QUICK=0
for arg in "$@"; do
  case "$arg" in
    --quick)    QUICK=1 ;;
    --help|-h)  sed -n '2,6p' "$0"; exit 0 ;;
  esac
done

if [[ "$QUICK" == "1" ]]; then
  export FUZZ_MAX_EXAMPLES="${FUZZ_MAX_EXAMPLES:-20}"
  CLI_MAX="--hypothesis-max-examples 20"
else
  export FUZZ_MAX_EXAMPLES="${FUZZ_MAX_EXAMPLES:-75}"
  CLI_MAX="--hypothesis-max-examples 75"
fi

echo "================================================================"
echo " Graylayer Fuzz — settings"
echo "   FUZZ_MAX_EXAMPLES = $FUZZ_MAX_EXAMPLES"
echo "   FUZZ_RATE_LIMIT_SLEEP = ${FUZZ_RATE_LIMIT_SLEEP:-0.25}"
echo "================================================================"

# ── 1. Schemathesis CLI against the gateway spec (safe mode: GET only) ──
#    We also run it via pytest below to collect rich findings; the CLI
#    run produces a compact terminal report we redirect to results/.
echo ">> schemathesis CLI → gateway spec"
schemathesis run specs/market_proxy.yaml \
  --base-url "${GRAYLAYER_GATEWAY_URL:-https://gateway.graylayer.tech}" \
  --header "X-API-Key:${GRAYLAYER_GATEWAY_API_KEY:-}" \
  --checks all \
  --include-method GET \
  $CLI_MAX \
  > results/schemathesis_gateway.txt 2>&1 || true

# ── 2. pytest: rich fuzz + negative + differential + stateful suites ──
echo ">> pytest suite"

PYTEST_ARGS=(-q -ra -m "gateway or negative or differential or stateful")

# Don't let test failures abort the script — we *want* failures in the reports.
pytest "${PYTEST_ARGS[@]}" || true

# ── 3. Summary + plots ──
echo ">> summarize"
python scripts/summarize.py

echo ""
echo "Done. Artifacts in results/:"
ls -la results/ | sed 's/^/    /'
