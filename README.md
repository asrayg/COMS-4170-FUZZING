# Graylayer Fuzz

Schema-guided fuzz testing of the [Graylayer](https://docs.graylayer.tech)
market-data API, for **COM S / SE 4170 Spring 2026** final project.

Two APIs are under test:

| Service | Base URL | Spec |
|---|---|---|
| Market Proxy (polymarket / kalshi / gemini / coinbase / forecastex) | `http://gateway.graylayer.tech` | [`specs/market_proxy.yaml`](specs/market_proxy.yaml) |
| Orderbook History (snapshots + deltas) | `http://data.graylayer.tech` | [`specs/orderbook_history.yaml`](specs/orderbook_history.yaml) |

Neither API publishes a machine-readable spec; both YAML files here were
authored from the documentation as a project artifact.

## What this project does

Four complementary techniques target each API:

1. **Schema-guided fuzzing** with [Schemathesis](https://schemathesis.readthedocs.io)
   — generates diverse, schema-valid inputs for every operation and runs
   them through built-in + custom response checks.
2. **Hand-crafted negative tests** (`fuzz/negatives.py`) — path traversal,
   null bytes, type confusion, boundary overflow, enum typos, oversize
   payloads.
3. **Differential / invariant tests** (`fuzz/differential.py`) — semantic
   cross-endpoint properties: midpoint ∈ [best_bid, best_ask], spread ≥ 0,
   snapshot rows sorted by `ts`, delta `sequence` monotone,
   `count == len(rows)`, anonymous access clamped to 1 day, etc.
4. **Stateful linked-operation tests** (`fuzz/stateful.py`) — list →
   detail handoffs: every ID a list endpoint returns must resolve at the
   corresponding detail endpoint.

## Quick start

```bash
# 1. set up
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. configure
cp .env.example .env
# then edit .env and paste in your API keys
#   GRAYLAYER_GATEWAY_API_KEY=...
#   GRAYLAYER_DATA_API_KEY=...

# 3. smoke check (no network)
python scripts/smoke.py

# 4. run everything
./scripts/run_all.sh             # full run, ~10–20 min
./scripts/run_all.sh --quick     # small, ~2 min
./scripts/run_all.sh --gateway   # only gateway suite
./scripts/run_all.sh --data      # only orderbook-history suite
```

Outputs land in `results/`:

```
results/
├── gateway_findings.jsonl           # append-only log of every event
├── gateway_findings.json            # consolidated at end of run
├── data_findings.jsonl              # same, for data.graylayer.tech
├── data_findings.json
├── negative_findings.jsonl          # hand-crafted negative cases
├── differential_findings.jsonl      # invariant violations
├── stateful_findings.jsonl          # list→detail handoff bugs
├── schemathesis_gateway.txt         # raw CLI output (for screenshots)
├── schemathesis_data.txt
├── pytest_report.html               # rich pytest report
├── pytest_report.json
├── summary.md                       # paper-ready tables
├── summary.csv                      # flat table, pandas-readable
├── by_endpoint.png                  # bar chart
└── by_severity.png                  # bar chart
```

## Project layout

```
graylayer-fuzz/
├── specs/                           # OpenAPI 3 specs (authored from docs)
│   ├── market_proxy.yaml
│   └── orderbook_history.yaml
├── fuzz/                            # shared library
│   ├── config.py                    # .env + constants
│   ├── reporting.py                 # Finding dataclass, JSONL writer, classifier
│   ├── hooks.py                     # schemathesis hooks + 4 custom checks
│   ├── negatives.py                 # 25+ hand-crafted malformed inputs
│   ├── differential.py              # 8 cross-endpoint invariants
│   └── stateful.py                  # 3 linked-operation flows
├── tests/                           # pytest suites
│   ├── conftest.py                  # shared reporter fixtures
│   ├── test_gateway_fuzz.py         # schemathesis → gateway
│   ├── test_data_fuzz.py            # schemathesis → data
│   ├── test_negative.py             # negative cases
│   ├── test_differential.py         # invariant cases
│   └── test_stateful.py             # stateful cases
├── scripts/
│   ├── run_all.sh                   # orchestrator
│   ├── summarize.py                 # JSONL → summary.md + plots
│   └── smoke.py                     # < 1 min sanity check
├── report/
│   └── report_template.md           # paper skeleton, ready to fill
├── results/                         # (populated at run time)
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

## Writing the report

1. Run `./scripts/run_all.sh`.
2. Open `results/summary.md` — the tables there (by service, by severity,
   top endpoints, high-severity findings) drop directly into the
   `## 4. Evaluation` section of `report/report_template.md`.
3. Pull 3–5 concrete high-severity cases from `results/*_findings.jsonl`
   into the _Representative findings_ subsection.
4. Convert the final markdown to PDF (`pandoc`, or just Markdown→PDF in
   Typora / VS Code).

## Screenshots to take for the report

- `schemathesis run ...` terminal output (`results/schemathesis_gateway.txt`)
- `pytest_report.html` opened in a browser
- 1–3 full failing cases from `*_findings.jsonl`
- `summary.md` rendered
- `by_endpoint.png`, `by_severity.png`

## Ethics / safety

- **GET only.** No state-mutating methods are fuzzed against production.
- **250 ms pause between requests** by default (see `FUZZ_RATE_LIMIT_SLEEP`
  in `.env.example`) so we are a good citizen of the shared service.
- **Documented 502 / 503 tolerated.** Our severity classifier treats them
  as upstream noise rather than Graylayer bugs.
- Reported issues, if any, are shared privately with the Graylayer team.

## References

See `report/report_template.md` for a full IEEE-style bibliography.
