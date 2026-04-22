"""Differential / invariant tests.

Each function in fuzz.differential returns a list of finding dicts. We
record them and fail the pytest case if any high-severity finding was
produced.
"""
from __future__ import annotations

import pytest

from fuzz.differential import ALL_DIFFERENTIAL_TESTS
from fuzz.reporting import Finding


@pytest.mark.differential
@pytest.mark.parametrize(
    "fn",
    ALL_DIFFERENTIAL_TESTS,
    ids=[f.__name__ for f in ALL_DIFFERENTIAL_TESTS],
)
def test_differential(fn, differential_reporter):
    findings = fn() or []
    for f in findings:
        differential_reporter.record(
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
        pytest.fail(f"{fn.__name__}: {len(high)} high-severity invariant violations: {msgs}")
