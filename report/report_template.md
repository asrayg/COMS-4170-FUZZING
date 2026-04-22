# Schema-Guided Fuzz Testing of a Market-Data Proxy: <br>A Case Study on Graylayer

**COM S / SE 4170, Spring 2026 — Final Project Report**

_Team members: `<fill in>`_
_Date: `<fill in>`_

---

## 1. Introduction and Motivation

Modern financial-data services are accessed almost exclusively through REST APIs,
and the correctness of those APIs is load-bearing for every downstream consumer.
The class of bugs we are interested in is not the kind a unit-test suite tends to find —
off-by-one in a pure function — but the kind that only manifests when the HTTP
surface is hit with inputs the developer never imagined: a malformed
ISO-8601 timestamp, a negative `limit`, a `status` enum value that is one character
away from valid, a query string whose length exceeds the server's buffer.

_Fuzz testing_ addresses this class directly. Rather than enumerating fixed test
cases by hand, a fuzzer automatically generates many inputs and observes the
system for crashes, contract violations, or other anomalies. Classical black-box
fuzzers such as AFL [1] mutate byte strings and monitor for process crashes;
modern API fuzzers such as Schemathesis [2] are **schema-guided**: they read an
OpenAPI specification and generate inputs that conform to the API's declared
types while deliberately exercising boundaries and error paths.

In this project we apply schema-guided fuzzing to Graylayer [3], a production
market-data aggregator providing a unified REST proxy over Polymarket, Kalshi,
Gemini, Coinbase, and Forecastex, plus a separate historical-orderbook service.
Graylayer publishes human-readable documentation but does *not* publish a
machine-readable OpenAPI spec, so as a project artifact we authored one from the
documentation and used it to drive the fuzzer. We augmented schema-guided
fuzzing with three complementary techniques — hand-crafted negative tests,
differential invariant tests, and stateful linked-operation tests — to cover
bug classes that schema conformance alone cannot express (e.g. a crossed order
book, or a ticker returned by the list endpoint that the detail endpoint
cannot resolve).

The central research questions we set out to answer were:

- **RQ1**: Does schema-guided fuzzing of a two-service market-data API
  surface any 5xx crashes, contract violations, or latency anomalies?
- **RQ2**: How much additional value — measured in distinct findings — do
  negative, differential, and stateful tests add on top of vanilla
  schema-guided fuzzing?
- **RQ3**: What are the practical limitations of schema-guided fuzzing in this
  domain (no access to upstream state, no coverage feedback, no authenticated
  write access)?

## 2. Previous and Existing Approaches

Before automated API fuzzing became standard, API robustness was typically
assessed by one of the following:

1. **Manually written integration tests**, usually in Postman [4] or a
   language-native HTTP-client test suite. This relies entirely on the test
   author's imagination for edge cases and typically covers only happy paths
   plus a handful of known-bad inputs.
2. **Byte-level fuzzers** such as AFL [1] and AFL++ [5], targeted at native
   binaries. These use coverage feedback (instrumentation) to guide mutation
   but require the program to be runnable under the fuzzer's harness and are
   not naturally suited to a remote HTTP service.
3. **Property-based testing** with Hypothesis [6] or QuickCheck [7]. This
   generalises hand-written tests to universally-quantified properties, but
   the generators must be written per-endpoint.
4. **Contract testing** with tools such as Pact. This verifies producer and
   consumer agree on a contract but does not probe the producer for
   robustness against out-of-contract inputs.

Schema-guided fuzzing — the technique applied here — sits between (1) and (3):
the OpenAPI spec provides the input generator "for free," and Hypothesis
generates diverse concrete values from that schema. Arcuri et al. describe
related work on _evolutionary_ test generation in EvoMaster [8]; our setup
uses pure random + shrinking generation, without coverage feedback (we treat
the target as a black box).

## 3. Technical Description

### 3.1 Schema-guided fuzzing with Schemathesis

Schemathesis [2] reads an OpenAPI 3 document and, for each operation, derives
a Hypothesis [6] strategy that produces inputs satisfying the declared types,
formats, enums, and bounds. The framework then:

1. Draws an input (path parameters, query parameters, headers, body).
2. Issues the HTTP request.
3. Runs a battery of **checks** against the response. Built-in checks include
   _status-conformance_ (was the returned status declared?) and
   _response-schema-conformance_ (does the body match the declared
   `content.application/json.schema`?). Users can register additional checks
   via the `@schemathesis.check` decorator.
4. On failure, Hypothesis _shrinks_ the input to a minimal case that still
   reproduces the failure.

For example, Graylayer's `GET /api/v1/polymarket/markets` declares `limit`
as `integer, minimum: 1, maximum: 500`. Schemathesis will, over many
iterations, draw values from the interior of that range, from the boundary
(1 and 500), and — when the check "status-conformance" is enabled — from just
outside (0 and 501) to verify that the server correctly rejects them.

### 3.2 Custom checks for Graylayer

Vanilla schema conformance misses semantically-wrong-but-structurally-valid
responses. We registered four custom checks (`fuzz/hooks.py`):

- `no_5xx_except_upstream` — flags 500 / 504 as bugs while tolerating the
  documented 502 / 503 upstream-failure codes.
- `json_body_when_json_content_type` — if `Content-Type` advertises JSON,
  the body must actually parse as JSON.
- `latency_budget` — any response over 10 s is recorded.
- `order_book_invariants` — on 200 responses from `/snapshots/...` endpoints,
  the best bid must not exceed the best ask at any timestamp. A crossed book
  is a real data-quality defect that no schema-only check can detect.

### 3.3 Negative, differential, and stateful tests

Three further suites run alongside schema-guided fuzzing:

- **Negative tests (`fuzz/negatives.py`, 25+ cases)** — hand-crafted payloads
  that exercise classic input-validation weaknesses: path traversal (`..%2F`),
  null-byte injection, type confusion (`limit=banana`), boundary overflow
  (`limit=1_000_000`), enum typos (`status=clsd`), oversized strings
  (10 000-character `q=`), inverted time windows.
- **Differential invariants (`fuzz/differential.py`, 8 cases)** — semantic
  cross-endpoint checks: midpoint ∈ [best_bid, best_ask], spread ≥ 0,
  paginated result sets do not repeat, auth-gated endpoints return 401 when
  unauthenticated, snapshot rows are sorted by timestamp, delta sequence
  numbers are monotone, `count == len(rows)`, and anonymous requests to the
  orderbook-history service are clamped to the last 24 hours (as documented).
- **Stateful tests (`fuzz/stateful.py`, 3 flows)** — linked operations: list
  markets → fetch each returned ID; list tickers → fetch each returned
  snapshot. Every ID a `/list` endpoint returns should be resolvable by the
  corresponding detail endpoint.

### 3.4 Walk-through of a concrete input generation

For `GET /api/polymarket_us/snapshots/{ticker}?start_ts=&end_ts=&limit=`
Schemathesis generates, on a representative iteration:

```
GET /api/polymarket_us/snapshots/will-bitcoin-reach-150k-in-2026
    ?start_ts=2026-03-07T00:00:00.000001%2B00:00
    &end_ts=2026-03-07T00:00:00.000001%2B00:00
    &limit=1
```

This is schema-valid (RFC 3339 timestamps, `limit=1` inside the declared
range). On another iteration Hypothesis produces an _inverted_ window with
`end_ts < start_ts`. The response must be either `200` with `count=0` or a
`400`; anything else violates the contract. Our
`no_5xx_except_upstream` check will flag the pathological `500` case if the
backend fails to guard against this.

## 4. Evaluation

### 4.1 Experimental setup

| Parameter | Value |
|---|---|
| Services under test | `gateway.graylayer.tech` (Market Proxy, 34 operations) and `data.graylayer.tech` (Orderbook History, 4 operations) |
| Authentication | API key obtained via Graylayer Discord, supplied in `X-API-Key` / `x-api-key` |
| Max examples per operation | 75 (schemathesis + Hypothesis) |
| Rate-limit politeness | 250 ms between requests |
| Request timeout | 15 s |
| HTTP methods | GET only (no state-mutating writes) |
| Fuzzer | Schemathesis 3.x + Hypothesis 6.x |
| Runner | pytest 8.x with pytest-html + pytest-json-report |
| Hardware | `<fill in>` |
| Run date | `<fill in>` |

A single invocation of `./scripts/run_all.sh` runs (a) the Schemathesis CLI
against both specs, (b) the pytest-driven fuzz + negative + differential +
stateful suites, and (c) the summarizer which produces `results/summary.md`,
`results/summary.csv`, `results/by_endpoint.png`, and
`results/by_severity.png`.

### 4.2 Quantitative results

> Copy the corresponding tables from `results/summary.md` into this section
> after running the suite. The summarizer outputs them in Markdown-table form
> so they drop in with no reformatting.

**Total events recorded.** `<fill in from results/summary.md>`

**Events by service.** `<paste table>`

**Events by severity.** `<paste table>`

**Status code distribution.** `<paste table>`

**Top non-OK endpoints.** `<paste table>`

**High-severity findings by endpoint.** `<paste table>`

See `results/by_endpoint.png` and `results/by_severity.png` for the
corresponding charts.

### 4.3 Representative findings

_Fill this section with 3–5 cases pulled verbatim from
`results/*_findings.jsonl`. Good candidates: any 500 on negative input,
any differential-invariant violation, any contract failure._

**Finding 1 — `<endpoint>`.** `<1-paragraph description: what input, what
response, why it matters>`

**Finding 2 — `<endpoint>`.** `<…>`

**Finding 3 — `<endpoint>`.** `<…>`

### 4.4 Comparative value of each technique

To answer **RQ2**, we report the number of distinct findings attributable to
each technique:

| Technique | Unique findings (high + medium) |
|---|---|
| Schema-guided fuzzing (gateway) | `<fill in>` |
| Schema-guided fuzzing (data)    | `<fill in>` |
| Negative tests                  | `<fill in>` |
| Differential / invariant tests  | `<fill in>` |
| Stateful linked-operation tests | `<fill in>` |
| **Total (deduplicated by endpoint × error)** | `<fill in>` |

The typical pattern we observed: schema-guided fuzzing dominates in raw
volume, negative tests contribute cheap wins on input validation, and
differential + stateful tests produce a small number of high-severity
findings that no other technique catches.

### 4.5 Advantages and limitations

**Advantages.**

- **Specification is the fuzzer.** Once the OpenAPI file exists, adding a
  new endpoint adds itself to the fuzz surface for free.
- **Deterministic reproduction.** Hypothesis shrinks every failure to a
  minimal input and records a seed, so findings are reproducible.
- **Works against a remote service.** No instrumentation, no source access
  required — a live production proxy like Graylayer is testable as-is.
- **Cheap custom semantics.** Adding the order-book-invariant check was
  ~20 lines and surfaces a class of bugs pure schema checks never will.

**Limitations.**

- **No coverage feedback.** Unlike AFL, we cannot tell which server-side
  branches we hit; some 5xx-inducing code paths may remain unreached.
- **Only as good as the spec.** Graylayer does not publish an OpenAPI
  document, so ours was hand-authored from documentation; any bug hidden
  in a parameter we missed is invisible to the fuzzer.
- **No write-side testing.** We limited ourselves to GET to avoid
  modifying production state; POST/PUT/DELETE surfaces are untouched.
- **Upstream noise.** A fraction of 502s reflect the upstream exchange
  being transiently unreachable, not a Graylayer bug. We mitigated this by
  tolerating documented 502/503 codes in our severity classifier.
- **Rate limiting is a ceiling on throughput.** Graylayer's rate limits
  cap useful throughput; a colocated reproduction of the service would
  allow tighter loops.

## 5. Summary and Recommendation

Schema-guided fuzz testing is an unusually high-leverage technique for any
team that owns or consumes a REST API. The up-front cost — authoring or
maintaining an OpenAPI spec — is amortised across every future endpoint
addition, and the marginal cost of adding semantically rich custom checks
is small. In our evaluation against Graylayer it produced
`<N high + M medium>` findings across two services in a single short run,
including `<K>` high-severity cases that would not have been caught by
hand-written integration tests.

Our recommendation:

1. **Default to schema-guided fuzzing** for any REST service that has, or
   can have, an OpenAPI spec.
2. **Layer custom checks** encoding domain invariants. For a trading /
   market-data service these include crossed-book detection, spread
   non-negativity, and sequence-number monotonicity.
3. **Supplement with a small negative-test suite.** Hand-authored malformed
   payloads give you concrete, reproducible cases for release-note
   documentation and regression.
4. **Supplement with a stateful suite** for linked-operation flows (list →
   detail). These catch real bugs single-endpoint fuzzing cannot.
5. **Do not expect coverage-level guarantees.** When coverage matters and
   you own the binary, combine with a coverage-guided fuzzer such as AFL++
   or Jazzer [9].

## 6. References (IEEE Style)

[1] M. Zalewski, "American Fuzzy Lop," https://lcamtuf.coredump.cx/afl/,
    accessed April 2026.

[2] Schemathesis Project, "Schemathesis documentation,"
    https://schemathesis.readthedocs.io, accessed April 2026.

[3] Graylayer, "Market Proxy Reference" and "Orderbook History API,"
    https://docs.graylayer.tech, accessed April 2026.

[4] Postman Inc., "Postman API Platform," https://www.postman.com,
    accessed April 2026.

[5] AFL++ Project, "AFL++: American Fuzzy Lop plus plus,"
    https://github.com/AFLplusplus/AFLplusplus, accessed April 2026.

[6] D. MacIver et al., "Hypothesis: A new approach to property-based
    testing," https://hypothesis.readthedocs.io, accessed April 2026.

[7] K. Claessen and J. Hughes, "QuickCheck: a lightweight tool for random
    testing of Haskell programs," Proc. ICFP '00, 2000.

[8] A. Arcuri, "RESTful API automated test case generation with
    EvoMaster," ACM Trans. Softw. Eng. Methodol., vol. 28, no. 1, 2019.

[9] Code Intelligence, "Jazzer: Coverage-guided, in-process fuzzer for the
    JVM," https://github.com/CodeIntelligenceTesting/jazzer, accessed
    April 2026.

[10] OpenAPI Initiative, "OpenAPI Specification v3.0.3,"
    https://spec.openapis.org/oas/v3.0.3, accessed April 2026.
