# COMS 4170 — Black-Box API Fuzzing Project

**Title:** Black-Box Fuzz Testing of the Graylayer Market Proxy API Using OpenAPI-Guided Test Generation

**Target:** [Graylayer](https://docs.graylayer.tech) — a market data proxy for Polymarket, Kalshi, Gemini, Coinbase, and Forecastex. Written in Rust.

---

## Quick facts

| Item | Value |
|------|-------|
| Base URL | `http://gateway.graylayer.tech/api/v1` |
| Auth | `X-API-Key` header |
| API docs | https://docs.graylayer.tech |
| OpenAPI spec | `openapi.yaml` (hand-authored from docs — no official spec exists) |
| Test tool | Schemathesis + pytest + Hypothesis |

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your API key:

```bash
cp .env.example .env
# Edit .env — get API key from #api-key-request in the Graylayer Discord
```

---

## Running the tests

### Read-only phase (safe against live endpoint)

```bash
source .venv/bin/activate
export $(cat .env | xargs)
pytest tests/ -m readonly -q
```

### Convenience script (saves JSON output)

```bash
bash scripts/run_readonly.sh
```

### CLI smoke test (no pytest, quick check)

```bash
schemathesis run openapi.yaml \
  --url http://gateway.graylayer.tech/api/v1 \
  -H "X-API-Key: $GRAYLAYER_API_KEY" \
  --hypothesis-max-examples 30
```

### All safe tests (no destructive)

```bash
pytest tests/ -m "not destructive" -q
```

### Save results to JSON

```bash
pytest tests/ -m readonly --json-report --json-report-file=results/run_$(date +%Y%m%d_%H%M%S).json
```

---

## Project Structure

```
.
├── openapi.yaml                  # Hand-authored from docs.graylayer.tech (no official spec)
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
├── README.md
├── tests/
│   ├── conftest.py               # Fixtures: base_url, auth_headers
│   └── test_graylayer_fuzz.py    # Three-phase fuzz test suite
├── results/                      # Saved JSON run reports (gitignored)
├── scripts/
│   └── run_readonly.sh           # One-command safe run
└── docs/
    ├── PROGRESSION.md            # 4-week timeline + 5-person work split
    └── report_outline.md         # Paper outline
```

---

## Endpoints covered

| Platform | Endpoints fuzzed | Auth required |
|----------|-----------------|---------------|
| Coinbase | products, ticker, book, trades, candles, currencies, time | No |
| Polymarket Gamma | markets, events, tags, search | Yes |
| Polymarket CLOB | book, price, midpoint, spread, trades, price history | Yes |
| Kalshi | exchange status, markets, orderbook, events, series | Yes |
| Gemini | categories, events, book, trades, ticker | Yes |
| Forecastex | contracts | Yes |

---

## Safety rules

- Default phase runs **read-only GET endpoints only**
- `max_examples=50` — keeps rate of requests low against live endpoint
- Phase 3 (`-m destructive`) is **never run against the live API** — sandbox only
- Do not commit `.env` — it is gitignored
