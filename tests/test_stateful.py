"""Stateful / linked-operation tests."""
from __future__ import annotations

import pytest

from fuzz.reporting import Finding
from fuzz.stateful import ALL_STATEFUL_TESTS


@pytest.mark.stateful
@pytest.mark.parametrize(
    "fn",
    ALL_STATEFUL_TESTS,
    ids=[f.__name__ for f in ALL_STATEFUL_TESTS],
)
def test_stateful(fn, stateful_reporter):
    findings = fn() or []
    for f in findings:
        stateful_reporter.record(
            Finding(
                service=f.get("service", "unknown"),
                endpoint=f.get("endpoint", "?"),
                method=f.get("method", "GET"),
                status=f.get("status"),
                category=f.get("category", "invariant"),
                severity=f.get("severity", "medium"),
                query=f.get("query"),
                path_params=f.get("path_params"),
                response_snippet=f.get("response_snippet"),
                error=f.get("error"),
            )
        )
    high = [f for f in findings if f.get("severity") == "high"]
    if high:
        msgs = "; ".join(f.get("error", "?") for f in high)
        pytest.fail(f"{fn.__name__}: {len(high)} high-severity findings: {msgs}")
