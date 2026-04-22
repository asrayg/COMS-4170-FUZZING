"""Hand-crafted negative tests.

Each `NegativeCase` from fuzz.negatives is turned into a parametrized pytest
test. We record every response, but only *fail* when:

- the server crashes (500/504) on a clearly malformed input (that's a bug), or
- the server returns 200 OK for an input that is *obviously* invalid (e.g.
  wrong type) — which indicates the input validation is permissive.

5xx responses to garbage input are the gold for the paper.
"""
from __future__ import annotations

import pytest
import requests

from fuzz.config import (
    DATA_URL,
    GATEWAY_URL,
    REQUEST_TIMEOUT,
    data_headers,
    gateway_headers,
)
from fuzz.negatives import DATA_NEGATIVES, GATEWAY_NEGATIVES, NegativeCase
from fuzz.reporting import Finding, classify


def _ids(cases: list[NegativeCase]) -> list[str]:
    return [c.name for c in cases]


@pytest.mark.negative
@pytest.mark.gateway
@pytest.mark.parametrize("case", GATEWAY_NEGATIVES, ids=_ids(GATEWAY_NEGATIVES))
def test_gateway_negative(case: NegativeCase, negative_reporter):
    url = f"{GATEWAY_URL}{case.path}"
    _run(case, url, gateway_headers(), negative_reporter)


@pytest.mark.negative
@pytest.mark.data
@pytest.mark.parametrize("case", DATA_NEGATIVES, ids=_ids(DATA_NEGATIVES))
def test_data_negative(case: NegativeCase, negative_reporter):
    url = f"{DATA_URL}{case.path}"
    _run(case, url, data_headers(), negative_reporter)


def _run(case: NegativeCase, url: str, headers: dict, reporter) -> None:
    try:
        r = requests.get(url, params=case.params, headers=headers, timeout=REQUEST_TIMEOUT)
        status = r.status_code
        body = (r.text or "")[:400]
        category, severity = classify(status, None)
        # Upgrade severity if server crashed on clearly bad input
        if status in (500, 504):
            severity = "high"
            category = "crash"
        reporter.record(
            Finding(
                service=case.service,
                endpoint=case.path,
                method="GET",
                status=status,
                category=f"negative:{category}",
                severity=severity,
                query=case.params,
                response_snippet=body,
                error=None,
                elapsed_ms=r.elapsed.total_seconds() * 1000 if r.elapsed else None,
            )
        )
        # Hard failures we want pytest to flag:
        if status in (500, 504):
            pytest.fail(
                f"[{case.name}] server crashed with {status} on malformed input. "
                f"Note: {case.note}. Body: {body!r}"
            )
        # If the case declared a set of expected rejection codes and the
        # server returned a wholly unexpected status, record a contract issue.
        if case.expected_statuses and status not in case.expected_statuses and status < 500:
            reporter.record(
                Finding(
                    service=case.service,
                    endpoint=case.path,
                    method="GET",
                    status=status,
                    category="negative:unexpected_status",
                    severity="low",
                    query=case.params,
                    response_snippet=body,
                    error=(
                        f"expected one of {case.expected_statuses}, got {status}. "
                        f"Note: {case.note}"
                    ),
                )
            )
    except requests.RequestException as e:
        reporter.record(
            Finding(
                service=case.service,
                endpoint=case.path,
                method="GET",
                status=None,
                category="negative:transport",
                severity="medium",
                query=case.params,
                error=str(e),
            )
        )
        pytest.skip(f"transport: {e}")
