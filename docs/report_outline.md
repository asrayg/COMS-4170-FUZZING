# Paper Outline

**Title:** Black-Box Fuzz Testing of the Graylayer API Using OpenAPI-Guided Test Generation

---

## 1. Introduction / Motivation (~0.5 page)

- APIs are external-facing attack surfaces that process untrusted input
- Manual test suites only cover cases developers think of
- Fuzzing discovers unexpected behavior at scale: crashes, contract violations, bad error handling
- Graylayer is a suitable target: documented API, structured inputs, live endpoint
- Research question: can schema-guided fuzzing find issues that manual tests would miss?

---

## 2. Previous / Existing Approaches (~1 page)

- Manual API testing (curl, Postman)
- Hand-written pytest integration tests
- Fixed negative test cases
- Limitations: labor-intensive, incomplete coverage, misses edge cases
- Prior fuzzing tools: AFL (source-level, coverage-guided), LibFuzzer, OWASP ZAP (API scanning)
- Gap: most tools require source code or are not schema-aware

---

## 3. Technical Description (~1.5 pages)

### 3.1 What is Fuzzing?
- Automated generation of unexpected/malformed inputs
- Goal: trigger crashes, errors, or unexpected behavior

### 3.2 Schema-Guided vs. Random Fuzzing
- Random fuzzing: generate arbitrary bytes → useful for binary formats
- Schema-guided fuzzing: use API schema to generate structurally valid but semantically varied inputs
- More efficient for APIs: respects data types, enums, required fields

### 3.3 How Schemathesis Works
- Reads OpenAPI spec (YAML/JSON)
- Uses Hypothesis (property-based testing) as the generation engine
- For each endpoint: generates request params, headers, bodies from schema types
- Sends requests to live endpoint
- Checks: no 5xx, response matches declared schema, JSON is parseable
- Shrinks failing examples to minimal reproducible case

### 3.4 Our Setup
- Python + Schemathesis + pytest
- Three test phases: read-only, auth rejection, destructive (sandbox only)
- Environment variables for credentials
- Results saved as JSON for analysis

---

## 4. Evaluation (~1.5 pages)

### 4.1 Environment
- Target: Graylayer API (Rust backend, live endpoint)
- Tool: Schemathesis 3.x, Python 3.11+
- Schema: openapi.yaml (X endpoints)

### 4.2 Methodology
- Phase 1: GET endpoints, 50 generated cases per endpoint
- Phase 2: auth rejection validation
- Recorded all 4xx/5xx responses

### 4.3 Results Table

| Endpoint | Method | Cases Generated | Result |
|----------|--------|-----------------|--------|
| /markets | GET | 50 | Passed |
| /orderbook | GET | 50 | 2 schema mismatches |
| /trades | GET | 50 | 1 × 500 on malformed param |
| ... | | | |

*(Fill in with real data from your runs)*

### 4.4 Key Findings
- Describe any 5xx errors found and what caused them
- Describe any schema violations
- Describe any interesting 4xx patterns
- Screenshots of terminal output + pytest summary

### 4.5 What the Tool Struggled With
- Stateful endpoints (e.g., order placement requires prior state)
- Auth flows that are not self-contained
- Endpoints with under-specified schemas

---

## 5. Limitations (~0.5 page)

- No source-level coverage: cannot confirm which code paths were exercised
- Depends on OpenAPI spec quality: missing or wrong schemas produce noisy results
- Cannot test stateful workflows automatically
- May miss logic bugs that don't surface as crashes or schema violations
- Rate limiting and live endpoint stability affect reproducibility
- Contrast with AFL: AFL instruments binary, tracks branch coverage, guides mutation toward uncovered paths — fundamentally deeper but requires source access

---

## 6. Summary and Recommendation (~0.5 page)

- Schema-guided fuzzing is practical and effective for black-box API testing
- Found X issues that manual tests would likely have missed
- Recommended for: teams with an OpenAPI spec and a staging environment
- Not a replacement for source-level fuzzing or formal verification
- Suggest: integrate Schemathesis into CI pipeline, run against staging on every PR

---

## 7. References

- Schemathesis documentation: https://schemathesis.readthedocs.io
- Hypothesis documentation: https://hypothesis.readthedocs.io
- AFL (American Fuzzy Lop): https://lcamtuf.coredump.cx/afl/
- OWASP ZAP: https://www.zaproxy.org
- Course readings on fuzzing (cite specific papers from syllabus)
- Graylayer API documentation (cite as accessed date)
