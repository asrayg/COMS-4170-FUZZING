"""Schemathesis hooks and custom response checks.

These are registered with `@schemathesis.hook` and `@schemathesis.check`.
They apply globally once imported, so `tests/conftest.py` imports this module.
"""
from __future__ import annotations

import time
from typing import Any

import schemathesis
from schemathesis import Case
from schemathesis.internal.checks import CheckContext

from .config import (
    GATEWAY_KEY,
    RATE_LIMIT_SLEEP,
)

# ──────────────────────────────────────────────────────────────────────────────
# Request hooks
# ──────────────────────────────────────────────────────────────────────────────

@schemathesis.hook
def before_call(context, case: Case) -> None:
    """Inject auth headers + a short sleep between requests (politeness)."""
    headers = dict(case.headers or {})

    if GATEWAY_KEY:
        headers["X-API-Key"] = GATEWAY_KEY

    headers.setdefault("User-Agent", "graylayer-fuzz/1.0 (COM S 4170 project)")
    headers.setdefault("Accept", "application/json")
    case.headers = headers

    if RATE_LIMIT_SLEEP > 0:
        time.sleep(RATE_LIMIT_SLEEP)


# ──────────────────────────────────────────────────────────────────────────────
# Custom checks
# ──────────────────────────────────────────────────────────────────────────────

@schemathesis.check
def no_5xx_except_upstream(ctx: CheckContext, response, case: Case) -> None:
    """Fail on 500/504 but tolerate documented 502/503 (upstream failures).

    Per Graylayer docs: 502 = upstream error, 503 = upstream returned error.
    Those are expected behavior of a proxy, not a server bug. A 500 or 504
    on the gateway itself *is* a bug worth flagging.
    """
    bad = {500, 504, 505, 506, 507, 508, 510, 511}
    if response.status_code in bad:
        raise AssertionError(
            f"Server-side crash: {response.status_code} on "
            f"{case.method} {case.path} "
            f"(body snippet: {response.text[:200]!r})"
        )


@schemathesis.check
def json_body_when_json_content_type(ctx: CheckContext, response, case: Case) -> None:
    """If Content-Type claims JSON, body must actually parse as JSON."""
    ctype = response.headers.get("Content-Type", "")
    if "application/json" in ctype and response.content:
        try:
            response.json()
        except Exception as e:  # noqa: BLE001
            raise AssertionError(
                f"Content-Type advertises JSON but body is not valid JSON: {e}"
            )


@schemathesis.check
def latency_budget(ctx: CheckContext, response, case: Case) -> None:
    """Any endpoint taking >10s is worth flagging for the paper."""
    elapsed = getattr(response, "elapsed", None)
    if elapsed is not None and elapsed.total_seconds() > 10:
        raise AssertionError(
            f"Slow response: {elapsed.total_seconds():.2f}s on {case.method} {case.path}"
        )


# Export the set of custom check names for use from tests
CUSTOM_CHECKS: tuple[Any, ...] = (
    no_5xx_except_upstream,
    json_body_when_json_content_type,
    latency_budget,
)
