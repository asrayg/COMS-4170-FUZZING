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
    DATA_KEY,
    DATA_URL,
    GATEWAY_KEY,
    GATEWAY_URL,
    RATE_LIMIT_SLEEP,
)

# ──────────────────────────────────────────────────────────────────────────────
# Request hooks
# ──────────────────────────────────────────────────────────────────────────────

@schemathesis.hook
def before_call(context, case: Case) -> None:
    """Inject auth headers + a short sleep between requests (politeness)."""
    # Determine which service this case belongs to by inspecting the server URL
    base = getattr(case.operation.schema, "base_url", "") or ""
    headers = dict(case.headers or {})

    if "gateway.graylayer.tech" in base and GATEWAY_KEY:
        headers.setdefault("X-API-Key", GATEWAY_KEY)
    elif "data.graylayer.tech" in base and DATA_KEY:
        headers.setdefault("x-api-key", DATA_KEY)

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


@schemathesis.check
def order_book_invariants(ctx: CheckContext, response, case: Case) -> None:
    """For snapshot endpoints, verify best bid <= best ask (no crossed book).

    Only runs on 200 JSON responses from snapshot endpoints. Failing this is
    a high-severity *semantic* bug that a vanilla schema check would miss.
    """
    if response.status_code != 200:
        return
    if "/snapshots/" not in case.path:
        return
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return
    rows = body.get("rows") if isinstance(body, dict) else None
    if not isinstance(rows, list) or not rows:
        return

    # Group by timestamp; at each ts, max(bid) must be <= min(ask).
    from collections import defaultdict
    by_ts: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"bid": [], "ask": []})
    for r in rows:
        ts = r.get("ts")
        side = r.get("side")
        price = r.get("price")
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            continue
        if ts and side in ("bid", "ask"):
            by_ts[ts][side].append(price_f)

    for ts, sides in by_ts.items():
        if sides["bid"] and sides["ask"]:
            best_bid = max(sides["bid"])
            best_ask = min(sides["ask"])
            if best_bid > best_ask:
                raise AssertionError(
                    f"Crossed book at {ts}: best_bid={best_bid} > best_ask={best_ask} "
                    f"on {case.method} {case.path}"
                )


# Export the set of custom check names for use from tests
CUSTOM_CHECKS: tuple[Any, ...] = (
    no_5xx_except_upstream,
    json_body_when_json_content_type,
    latency_budget,
    order_book_invariants,
)
