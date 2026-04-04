# Project Progression & Work Split

**Course:** COMS/SE 4170 — Software Testing
**Project:** Black-Box Fuzz Testing of the Graylayer Market Proxy API Using OpenAPI-Guided Test Generation
**Team size:** 5 people

---

## Timeline (4-week plan)

```
Week 1  │ Setup + Research
Week 2  │ Tool runs + Data collection
Week 3  │ Analysis + Writing
Week 4  │ Polish + Final submission
```

---

## Week-by-Week Milestones

### Week 1 — Setup & Research
**Goal:** Everyone understands the approach; environment is running.

| # | Task | Owner | Done? |
|---|------|-------|-------|
| 1.1 | Clone repo, create virtualenv, install deps | Person A | [ ] |
| 1.2 | Review docs.graylayer.tech; openapi.yaml already authored (no official spec exists) | Person B | [ ] |
| 1.3 | Get API key from #api-key-request in Graylayer Discord; confirm live endpoint works (curl /health) | Person C | [ ] |
| 1.4 | Read Schemathesis docs + run CLI smoke test | Person D | [ ] |
| 1.5 | Draft Introduction + Motivation section of paper | Person E | [ ] |

**Milestone check:** `pytest tests/ -m readonly -q` runs without crashing.

---

### Week 2 — Tool Runs & Data Collection
**Goal:** Actual fuzzing runs completed; raw results saved.

| # | Task | Owner | Done? |
|---|------|-------|-------|
| 2.1 | Run Phase 1 (GET endpoints, max_examples=50), save results | Person A | [ ] |
| 2.2 | Run Phase 2 (auth rejection tests), save results | Person B | [ ] |
| 2.3 | Manually investigate any 5xx or schema violations found | Person C | [ ] |
| 2.4 | Collect screenshots: terminal output, pytest summary, any failures | Person D | [ ] |
| 2.5 | Fill in results table (endpoint, method, cases, outcome) | Person E | [ ] |

**Milestone check:** `results/` folder has at least 2 saved JSON run reports.

---

### Week 3 — Analysis & Writing
**Goal:** Paper is ~80% drafted.

| # | Task | Owner | Done? |
|---|------|-------|-------|
| 3.1 | Write Technical Description section | Person A | [ ] |
| 3.2 | Write Previous / Existing Approaches section | Person B | [ ] |
| 3.3 | Write Evaluation section (use results table + screenshots) | Person C | [ ] |
| 3.4 | Write Limitations section | Person D | [ ] |
| 3.5 | Write Summary and Recommendation section | Person E | [ ] |

**Milestone check:** Full paper draft exists in shared doc.

---

### Week 4 — Polish & Submission
**Goal:** Final paper + code submitted.

| # | Task | Owner | Done? |
|---|------|-------|-------|
| 4.1 | Proofread full paper, unify voice | Persons A + B | [ ] |
| 4.2 | Add references / citations | Person C | [ ] |
| 4.3 | Clean up code, make sure repo runs from scratch | Person D | [ ] |
| 4.4 | Final review + submission | All | [ ] |

---

## Work Split by Role

Each person owns one primary role for the project. Everyone contributes to the paper.

---

### Person A — Project Lead / Infrastructure
**Owns:** repo setup, environment, CI, final code review

Responsibilities:
- Set up virtualenv, install deps, verify everything runs
- Own the `tests/` folder structure
- Run the final evaluation pass before submission
- Coordinate merges and keep the repo clean
- Write Technical Description section

---

### Person B — API Research & Spec Work
**Owns:** OpenAPI spec, endpoint inventory, Graylayer docs

Responsibilities:
- Obtain and validate `openapi.yaml` from Graylayer
- Document all endpoints tested: path, method, parameters
- Identify which endpoints are safe (read-only) vs. risky
- Update `SKIP_PATHS` in the test file if needed
- Write Previous / Existing Approaches section

---

### Person C — Tool Operator & Results Collector
**Owns:** running the fuzzer, saving output, investigating failures

Responsibilities:
- Run all three phases of tests
- Save JSON reports to `results/`
- Take screenshots of terminal output (for the paper)
- Investigate any 5xx or schema violations in detail
- Write the Evaluation section

---

### Person D — Analysis & Findings
**Owns:** interpreting results, building the results table, comparison

Responsibilities:
- Analyze saved results and categorize findings
- Build the results table (endpoint, cases generated, outcome)
- Compare Schemathesis vs. manual testing
- Research AFL / coverage-guided fuzzing for contrast
- Write Limitations section

---

### Person E — Writing Lead
**Owns:** paper coherence, intro, conclusion, references

Responsibilities:
- Draft Introduction + Motivation section
- Write Summary and Recommendation section
- Compile References section
- Ensure paper reads cohesively end-to-end
- Final proofread pass

---

## Paper Section Ownership Summary

| Section | Owner |
|---------|-------|
| Introduction / Motivation | Person E |
| Previous / Existing Approaches | Person B |
| Technical Description | Person A |
| Evaluation | Person C |
| Limitations | Person D |
| Summary & Recommendation | Person E |
| References | Person E |

---

## Shared Responsibilities

- All 5 people review and comment on every section before final submission
- All 5 people can run the fuzzer locally and contribute findings
- Use a shared Google Doc or Overleaf for the paper draft
- Use this repo for all code

---

## Quick-Start for New Team Members

```bash
# 1. Clone and enter the project
cd COMS-4170-FUZZING

# 2. Set up virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Set credentials
cp .env.example .env
# Edit .env and fill in GRAYLAYER_BASE_URL and GRAYLAYER_TOKEN

# 4. Add the OpenAPI spec
# Place openapi.yaml in the project root

# 5. Run a smoke test
pytest tests/ -m readonly -q
```

---

## Notes

- Do NOT commit `.env` or tokens. It is in `.gitignore`.
- Do NOT run destructive tests (`-m destructive`) against the live endpoint without confirming it's a sandbox.
- If the live endpoint is rate-limited, lower `max_examples` in the test file.
- Save every run's results to `results/` so you have evidence for the paper.
