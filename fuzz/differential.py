"""Differential / invariant tests.

These run *after* fuzzing with real inputs and check *semantic* properties
that OpenAPI alone cannot express. They're cheap, deterministic, and give
the report concrete cross-endpoint findings to cite.

Each test function returns a list of Finding-like dicts. A test harness in
tests/test_differential.py drives them.
"""
from __future__ import annotations

from typing import Any

import requests

from .config import GATEWAY_URL, REQUEST_TIMEOUT, gateway_headers


def _get(url: str, headers: dict[str, str], params: dict | None = None) -> tuple[int, Any]:
    try:
        r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = r.text
        return r.status_code, body
    except requests.RequestException as e:
        return 0, {"error": str(e)}


def gw_documented_platforms_reachable() -> list[dict]:
    """Every documented platform must be reachable through the gateway.

    The spec advertises polymarket-us, kalshi, coinbase, gemini, forecastex.
    A 4xx with body `Unknown platform` indicates the platform integration is
    missing entirely — distinct from a bad-input 400.
    """
    findings: list[dict] = []
    probes = [
        ("polymarket-us", "/api/v1/polymarket-us/markets"),
        ("kalshi",        "/api/v1/kalshi/markets"),
        ("coinbase",      "/api/v1/coinbase/products"),
        ("gemini",        "/api/v1/gemini/v1/symbols"),
        ("forecastex",    "/api/v1/forecastex/contracts"),
    ]
    for platform, path in probes:
        s, body = _get(f"{GATEWAY_URL}{path}", gateway_headers())
        body_text = body if isinstance(body, str) else (
            (body or {}).get("error", "") if isinstance(body, dict) else ""
        )
        if isinstance(body_text, str) and "Unknown platform" in body_text:
            findings.append({
                "service": "gateway",
                "endpoint": path,
                "category": "invariant",
                "severity": "high",
                "status": s,
                "error": f"documented platform {platform!r} returns 'Unknown platform' — integration is dead",
            })
    return findings


def gw_polymarket_us_book_no_crossed() -> list[dict]:
    """For a Polymarket-US market book, max(bid.price) must be <= min(offer.price).

    Pulls a few markets from /markets, fetches /markets/{slug}/book for each,
    and checks the order book is not crossed.
    """
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/markets",
                   gateway_headers(), {"limit": 10, "active": True})
    if s != 200 or not isinstance(body, dict):
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/polymarket-us/markets",
            "category": "precondition",
            "severity": "info",
            "status": s,
            "error": f"precondition failed: polymarket-us markets list returned {s}",
        })
        return findings
    markets = body.get("markets") or []
    checked = 0
    for m in markets:
        if checked >= 5:
            break
        slug = m.get("slug") if isinstance(m, dict) else None
        if not slug:
            continue
        s2, book = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/markets/{slug}/book",
                        gateway_headers())
        if s2 != 200 or not isinstance(book, dict):
            continue
        md = book.get("marketData") or {}
        bids = md.get("bids") or []
        offers = md.get("offers") or md.get("asks") or []
        try:
            best_bid = max(float(b.get("price")) for b in bids if b.get("price") is not None)
            best_ask = min(float(a.get("price")) for a in offers if a.get("price") is not None)
        except (TypeError, ValueError):
            continue
        checked += 1
        if best_bid > best_ask + 1e-9:
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/polymarket-us/markets/{slug}/book",
                "category": "invariant",
                "severity": "high",
                "error": f"crossed book on {slug}: best_bid={best_bid} > best_ask={best_ask}",
                "path_params": {"slug": slug},
            })
    return findings


def gw_gemini_book_no_crossed() -> list[dict]:
    """For a Gemini orderbook, max(bid.price) must be <= min(ask.price).

    A crossed book is a high-severity semantic bug — would let a client
    arbitrage a wrong number directly out of the proxy.
    """
    findings: list[dict] = []
    s, symbols = _get(f"{GATEWAY_URL}/api/v1/gemini/v1/symbols", gateway_headers())
    if s != 200 or not isinstance(symbols, list) or not symbols:
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/gemini/v1/symbols",
            "category": "precondition",
            "severity": "info",
            "status": s,
            "error": f"precondition failed: gemini symbols returned {s}",
        })
        return findings

    # sample a few liquid majors
    targets = [sym for sym in ("btcusd", "ethusd", "solusd") if sym in symbols]
    if not targets:
        targets = symbols[:3]

    for sym in targets:
        s, book = _get(f"{GATEWAY_URL}/api/v1/gemini/v1/book/{sym}", gateway_headers())
        if s != 200 or not isinstance(book, dict):
            continue
        try:
            best_bid = max(float(b["price"]) for b in book.get("bids") or [])
            best_ask = min(float(a["price"]) for a in book.get("asks") or [])
        except (TypeError, ValueError, KeyError):
            continue
        if best_bid > best_ask + 1e-9:
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/gemini/v1/book/{symbol}",
                "category": "invariant",
                "severity": "high",
                "error": f"crossed book on {sym}: best_bid={best_bid} > best_ask={best_ask}",
                "path_params": {"symbol": sym},
            })
    return findings


def gw_kalshi_pagination_monotone() -> list[dict]:
    """Cursor-paginated /kalshi/events: page 1 vs page 2 (via cursor)
    must not return the same event tickers — detects broken pagination."""
    findings: list[dict] = []
    s1, p1 = _get(f"{GATEWAY_URL}/api/v1/kalshi/events",
                  gateway_headers(), {"limit": 5})
    if s1 != 200 or not isinstance(p1, dict):
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/kalshi/events",
            "category": "precondition",
            "severity": "info",
            "status": s1,
            "error": f"precondition failed: kalshi events page 1 returned {s1}",
        })
        return findings
    cursor = p1.get("cursor")
    if not cursor:
        # one short page, can't test pagination — that's fine
        return findings
    s2, p2 = _get(f"{GATEWAY_URL}/api/v1/kalshi/events",
                  gateway_headers(), {"limit": 5, "cursor": cursor})
    if s2 != 200 or not isinstance(p2, dict):
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/kalshi/events",
            "category": "precondition",
            "severity": "info",
            "status": s2,
            "error": f"precondition failed: kalshi events page 2 returned {s2}",
        })
        return findings

    ids1 = {e.get("event_ticker") for e in (p1.get("events") or []) if isinstance(e, dict)}
    ids2 = {e.get("event_ticker") for e in (p2.get("events") or []) if isinstance(e, dict)}
    if ids1 and ids2 and ids1 == ids2:
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/kalshi/events",
            "category": "invariant",
            "severity": "medium",
            "error": "page 1 and page 2 (via cursor) returned identical event tickers",
        })
    return findings


def gw_auth_gate_consistency() -> list[dict]:
    """Endpoints that require auth must return 401 when no key is supplied.

    Probes only platforms that are reachable at the gateway.
    """
    findings: list[dict] = []
    probes = [
        "/api/v1/kalshi/markets",
        "/api/v1/coinbase/products",
        "/api/v1/gemini/v2/ticker/BTCUSD",
        "/api/v1/forecastex/contracts",
    ]
    headers = {"Accept": "application/json"}  # no X-API-Key
    any_reachable = False
    for p in probes:
        s, _ = _get(f"{GATEWAY_URL}{p}", headers)
        if s == 0:
            continue
        any_reachable = True
        if s != 401:
            findings.append({
                "service": "gateway",
                "endpoint": p,
                "category": "invariant",
                "severity": "medium",
                "status": s,
                "error": f"expected 401 without API key, got {s}",
            })
    if not any_reachable:
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/*",
            "category": "precondition",
            "severity": "info",
            "status": 0,
            "error": "precondition failed: no probe endpoints reachable",
        })
    return findings


ALL_DIFFERENTIAL_TESTS = [
    gw_documented_platforms_reachable,
    gw_polymarket_us_book_no_crossed,
    gw_gemini_book_no_crossed,
    gw_kalshi_pagination_monotone,
    gw_auth_gate_consistency,
]
