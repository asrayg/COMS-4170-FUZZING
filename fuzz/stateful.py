"""Stateful / linked-operation tests.

These simulate *realistic client flows* (list → pick an ID → fetch detail)
rather than treating every endpoint in isolation. They find bugs that
single-endpoint fuzzing cannot, e.g. an ID returned by the list endpoint
that can't be resolved by the detail endpoint.
"""
from __future__ import annotations

import random

import requests

from .config import DATA_URL, GATEWAY_URL, REQUEST_TIMEOUT, data_headers, gateway_headers


def _get(url: str, headers: dict, params: dict | None = None):
    try:
        r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, None
    except requests.RequestException as e:
        return 0, {"error": str(e)}


def gw_polymarket_list_then_detail() -> list[dict]:
    """List → pick 5 IDs → fetch each. Every listed ID must resolve (200)."""
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/polymarket/markets",
                   gateway_headers(), {"limit": 10})
    if s != 200 or not isinstance(body, list):
        return findings
    ids = [m.get("id") for m in body if isinstance(m, dict) and m.get("id")]
    for mid in ids[:5]:
        s2, _ = _get(f"{GATEWAY_URL}/api/v1/polymarket/markets/{mid}", gateway_headers())
        if s2 != 200:
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/polymarket/markets/{id}",
                "category": "invariant",
                "severity": "high",
                "status": s2,
                "error": f"id {mid!r} returned by list but detail endpoint returned {s2}",
                "path_params": {"id": mid},
            })
    return findings


def gw_kalshi_list_then_orderbook() -> list[dict]:
    """List Kalshi markets → pick 3 → fetch orderbook. Each should return 200."""
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/kalshi/markets",
                   gateway_headers(), {"limit": 5})
    if s != 200 or not isinstance(body, dict):
        return findings
    markets = body.get("markets") or []
    picks = [m.get("ticker") or m.get("market_id") for m in markets[:3]
             if isinstance(m, dict)]
    for mid in picks:
        if not mid:
            continue
        s2, _ = _get(f"{GATEWAY_URL}/api/v1/kalshi/markets/{mid}/orderbook",
                     gateway_headers())
        if s2 not in (200, 404):
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/kalshi/markets/{market_id}/orderbook",
                "category": "invariant",
                "severity": "medium",
                "status": s2,
                "error": f"orderbook for listed market {mid!r} returned {s2}",
                "path_params": {"market_id": mid},
            })
    return findings


def data_tickers_then_snapshot() -> list[dict]:
    """For each exchange: list tickers → randomly sample → fetch snapshot.
    Every listed ticker should be retrievable (200), not 404."""
    findings: list[dict] = []
    for exch in ("kalshi", "polymarket_us", "gemini"):
        s, body = _get(f"{DATA_URL}/api/{exch}/tickers", data_headers())
        if s != 200 or not isinstance(body, dict):
            continue
        tickers = body.get("tickers") or []
        if not tickers:
            continue
        # sample up to 3 random tickers to avoid biasing toward alphabetical order
        sampled = random.sample(tickers, k=min(3, len(tickers)))
        for t in sampled:
            s2, _ = _get(f"{DATA_URL}/api/{exch}/snapshots/{t}",
                         data_headers(), {"limit": 1})
            if s2 == 404:
                findings.append({
                    "service": "data",
                    "endpoint": f"/api/{exch}/snapshots/{{ticker}}",
                    "category": "invariant",
                    "severity": "high",
                    "status": 404,
                    "error": f"ticker {t!r} listed but returned 404 on snapshot fetch",
                    "path_params": {"ticker": t},
                })
            elif s2 >= 500 and s2 not in (502, 503):
                findings.append({
                    "service": "data",
                    "endpoint": f"/api/{exch}/snapshots/{{ticker}}",
                    "category": "crash",
                    "severity": "high",
                    "status": s2,
                    "error": f"ticker {t!r} caused {s2}",
                    "path_params": {"ticker": t},
                })
    return findings


ALL_STATEFUL_TESTS = [
    gw_polymarket_list_then_detail,
    gw_kalshi_list_then_orderbook,
    data_tickers_then_snapshot,
]
