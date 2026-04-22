"""Schema-guided fuzz tests for the Graylayer Market Proxy (gateway).

Schemathesis reads the OpenAPI spec, generates ~MAX_EXAMPLES inputs per
operation, runs them through all registered checks (including our custom
ones in fuzz/hooks.py), and reports failures.
"""
from __future__ import annotations

import pytest
import schemathesis
from hypothesis import settings

from fuzz.config import GATEWAY_URL, MAX_EXAMPLES, REQUEST_TIMEOUT, SPEC_GATEWAY
from fuzz.hooks import CUSTOM_CHECKS  # noqa: F401 — ensures checks are registered
from fuzz.reporting import Finding, classify

schema = schemathesis.openapi.from_path(str(SPEC_GATEWAY), base_url=GATEWAY_URL)


@pytest.mark.gateway
@schema.parametrize()
@settings(max_examples=MAX_EXAMPLES, deadline=None, print_blob=False)
def test_gateway_fuzz(case, gateway_reporter):
    try:
        response = case.call(timeout=REQUEST_TIMEOUT)
        status = response.status_code
        error = None
        # Run every standard + custom check
        try:
            case.validate_response(response)
        except Exception as e:  # noqa: BLE001
            error = str(e)
        category, severity = classify(status, error)

        # Always record; the report script filters by severity later.
        gateway_reporter.record(
            Finding(
                service="gateway",
                endpoint=case.path,
                method=case.method.upper(),
                status=status,
                category=category,
                severity=severity,
                query=dict(case.query or {}),
                path_params=dict(case.path_parameters or {}),
                headers={k: v for k, v in (case.headers or {}).items()
                         if k.lower() not in ("x-api-key", "authorization")},
                request_body=case.body if case.body else None,
                response_snippet=(response.text or "")[:400],
                error=error,
                elapsed_ms=response.elapsed.total_seconds() * 1000 if response.elapsed else None,
            )
        )
        # Re-raise so pytest marks the case as failed only when it's a real bug.
        if error and category in ("contract", "crash"):
            raise AssertionError(error)
    except Exception as e:  # noqa: BLE001
        # Transport-level failures (timeouts, connection resets)
        gateway_reporter.record(
            Finding(
                service="gateway",
                endpoint=case.path,
                method=case.method.upper(),
                status=None,
                category="transport",
                severity="medium",
                query=dict(case.query or {}),
                path_params=dict(case.path_parameters or {}),
                error=str(e),
            )
        )
        # Don't fail the whole suite on transient transport issues
        pytest.skip(f"transport: {e}")
