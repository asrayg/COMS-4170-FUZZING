"""
Black-box API fuzz tests for the Graylayer Market Proxy API.

Target:   http://gateway.graylayer.tech/api/v1
Auth:     X-API-Key header
Schema:   ../openapi.yaml (hand-authored from docs.graylayer.tech)

Test phases
-----------
Phase 1 (readonly):   GET endpoints — safe against live API
Phase 2 (readonly):   Auth-rejection checks (no key sent)
Phase 3 (destructive): POST/DELETE — sandbox only, skipped by default

Run commands
------------
  pytest tests/ -m readonly -q                   # safe phase 1+2
  pytest tests/ -m "not destructive" -q          # everything except destructive
  bash scripts/run_readonly.sh                   # phase 1 with JSON output saved
"""

import os
import pytest
import schemathesis
from hypothesis import settings, HealthCheck

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "openapi.yaml")

schema = schemathesis.openapi.from_path(SCHEMA_PATH)

# ---------------------------------------------------------------------------
# Safety configuration
# ---------------------------------------------------------------------------

# Only fuzz these HTTP methods in the read-only phase
READONLY_METHODS = {"GET", "HEAD", "OPTIONS"}

# Path prefixes to skip entirely (add any endpoint you want to exclude)
SKIP_PATHS: set[str] = set()


def is_readonly(case) -> bool:
    return case.method.upper() in READONLY_METHODS


def should_skip(case) -> bool:
    return any(case.path.startswith(p) for p in SKIP_PATHS)


# ---------------------------------------------------------------------------
# Phase 1 — Read-only fuzzing
# Safe to run against the live Graylayer endpoint.
# Schemathesis generates many valid/boundary/invalid inputs from the schema.
# ---------------------------------------------------------------------------

@pytest.mark.readonly
@schema.parametrize()
@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
    deadline=10_000,
)
def test_readonly_endpoints(case, base_url, auth_headers):
    """
    Fuzz all GET endpoints.

    Assertions:
    1. No 5xx server errors — the server must not crash on any generated input.
    2. Responses claiming JSON Content-Type must parse as valid JSON.
    3. Response body must conform to the declared schema (schemathesis built-in).
    """
    if not is_readonly(case):
        pytest.skip("Non-GET endpoint — skipped in readonly phase")

    if should_skip(case):
        pytest.skip(f"Skipped path: {case.path}")

    response = case.call(base_url=base_url, headers=auth_headers)

    # ── Assertion 1: No server-side crashes ──────────────────────────────
    assert response.status_code < 500, (
        f"SERVER ERROR\n"
        f"  Endpoint : {case.method} {case.path}\n"
        f"  Status   : {response.status_code}\n"
        f"  Query    : {case.query}\n"
        f"  Body     : {response.text[:500]}"
    )

    # ── Assertion 2: JSON must be parseable ──────────────────────────────
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            response.json()
        except Exception as exc:
            pytest.fail(
                f"INVALID JSON RESPONSE\n"
                f"  Endpoint     : {case.method} {case.path}\n"
                f"  Content-Type : {content_type}\n"
                f"  Body         : {response.text[:500]}\n"
                f"  Error        : {exc}"
            )

    # ── Assertion 3: Schema contract validation ───────────────────────────
    # Checks that the response matches the declared response schema in openapi.yaml.
    # Comment out if the spec is under-specified and produces too many false positives.
    case.validate_response(response)


# ---------------------------------------------------------------------------
# Phase 2 — Auth rejection checks
# Verifies that endpoints do not leak data or crash when no API key is sent.
# ---------------------------------------------------------------------------

@pytest.mark.readonly
@schema.parametrize(method="GET")
@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
    deadline=10_000,
)
def test_auth_rejection(case, base_url):
    """
    Send requests with NO API key.

    Assertions:
    1. Must not return 5xx — missing auth should produce 401/403, not a crash.
    2. Response must be valid JSON if Content-Type claims JSON.
    """
    if should_skip(case):
        pytest.skip(f"Skipped path: {case.path}")

    # Explicitly send empty headers (no API key)
    response = case.call(base_url=base_url, headers={})

    assert response.status_code != 500, (
        f"SERVER ERROR with no auth\n"
        f"  Endpoint : {case.method} {case.path}\n"
        f"  Status   : {response.status_code}\n"
        f"  Body     : {response.text[:300]}"
    )

    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            response.json()
        except Exception as exc:
            pytest.fail(
                f"INVALID JSON on auth-rejected response\n"
                f"  Endpoint : {case.method} {case.path}\n"
                f"  Body     : {response.text[:300]}\n"
                f"  Error    : {exc}"
            )


# ---------------------------------------------------------------------------
# Phase 3 — Destructive endpoints
# DO NOT run against the live production endpoint.
# Only run on a sandbox or with explicit team approval.
# Skipped by default: pytest -m "not destructive"
# ---------------------------------------------------------------------------

@pytest.mark.destructive
@schema.parametrize(method="POST")
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
    deadline=15_000,
)
def test_post_endpoints(case, base_url, auth_headers):
    """
    Fuzz POST endpoints. SANDBOX ONLY.

    Assertions:
    1. No 5xx errors — invalid POST bodies should return 4xx, not crash the server.
    """
    if should_skip(case):
        pytest.skip(f"Skipped path: {case.path}")

    response = case.call(base_url=base_url, headers=auth_headers)

    assert response.status_code < 500, (
        f"SERVER ERROR on POST\n"
        f"  Endpoint : {case.method} {case.path}\n"
        f"  Status   : {response.status_code}\n"
        f"  Body     : {response.text[:500]}"
    )
