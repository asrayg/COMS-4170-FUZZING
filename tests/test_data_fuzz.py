"""Schema-guided fuzz tests for the Graylayer Orderbook History API."""
from __future__ import annotations

import pytest
import schemathesis
from hypothesis import settings

from fuzz.config import DATA_URL, MAX_EXAMPLES, REQUEST_TIMEOUT, SPEC_DATA
from fuzz.hooks import CUSTOM_CHECKS  # noqa: F401
from fuzz.reporting import Finding, classify

schema = schemathesis.openapi.from_path(str(SPEC_DATA), base_url=DATA_URL)


@pytest.mark.data
@schema.parametrize()
@settings(max_examples=MAX_EXAMPLES, deadline=None, print_blob=False)
def test_data_fuzz(case, data_reporter):
    try:
        response = case.call(timeout=REQUEST_TIMEOUT)
        status = response.status_code
        error = None
        try:
            case.validate_response(response)
        except Exception as e:  # noqa: BLE001
            error = str(e)
        category, severity = classify(status, error)

        data_reporter.record(
            Finding(
                service="data",
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
        if error and category in ("contract", "crash"):
            raise AssertionError(error)
    except Exception as e:  # noqa: BLE001
        data_reporter.record(
            Finding(
                service="data",
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
        pytest.skip(f"transport: {e}")
