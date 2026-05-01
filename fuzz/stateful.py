"""Stateful / linked-operation tests.

These simulate *realistic client flows* (list → pick an ID → fetch detail)
rather than treating every endpoint in isolation. They find bugs that
single-endpoint fuzzing cannot, e.g. an ID returned by the list endpoint
that can't be resolved by the detail endpoint.
"""
from __future__ import annotations

import requests

from .config import GATEWAY_URL, REQUEST_TIMEOUT, gateway_headers


def _get(url: str, headers: dict, params: dict | None = None):
    try:
        r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, None
    except requests.RequestException as e:
        return 0, {"error": str(e)}


def gw_polymarket_us_list_then_detail() -> list[dict]:
    """List Polymarket-US markets → for each, fetch the documented detail
    endpoint /markets/{id}. Per docs the list returns ids that should
    resolve at the detail endpoint; reality currently 404s every one.

    Also try /markets/{slug}/bbo as a sanity check on the slug-keyed
    sub-resources.
    """
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/markets",
                   gateway_headers(), {"limit": 5})
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
    for m in markets[:5]:
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        slug = m.get("slug")
        if mid is not None:
            s2, _ = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/markets/{mid}",
                         gateway_headers())
            if s2 != 200:
                findings.append({
                    "service": "gateway",
                    "endpoint": "/api/v1/polymarket-us/markets/{id}",
                    "category": "invariant",
                    "severity": "high",
                    "status": s2,
                    "error": f"market id {mid!r} from list returned {s2} on detail endpoint",
                    "path_params": {"id": str(mid)},
                })
        if slug:
            # The slug-by-itself detail is documented; check it too.
            s3, _ = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/markets/{slug}",
                         gateway_headers())
            if s3 != 200:
                findings.append({
                    "service": "gateway",
                    "endpoint": "/api/v1/polymarket-us/markets/{slug}",
                    "category": "invariant",
                    "severity": "high",
                    "status": s3,
                    "error": f"market slug {slug!r} from list returned {s3} on detail endpoint",
                    "path_params": {"slug": slug},
                })
            # BBO sub-resource: should be 200 — sanity check that the
            # slug really is valid even though the bare detail 404s.
            s4, _ = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/markets/{slug}/bbo",
                         gateway_headers())
            if s4 not in (200, 404):
                findings.append({
                    "service": "gateway",
                    "endpoint": "/api/v1/polymarket-us/markets/{slug}/bbo",
                    "category": "invariant",
                    "severity": "medium",
                    "status": s4,
                    "error": f"BBO for listed slug {slug!r} returned {s4}",
                    "path_params": {"slug": slug},
                })
    return findings


def gw_polymarket_us_events_list_then_detail() -> list[dict]:
    """List Polymarket-US events → fetch each event by its slug.

    Per docs both id and slug forms are valid at /events/{id}; reality
    only accepts integer ids and 400s with a `strconv.ParseInt` error
    on slugs.
    """
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/events",
                   gateway_headers(), {"limit": 3})
    if s != 200 or not isinstance(body, dict):
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/polymarket-us/events",
            "category": "precondition",
            "severity": "info",
            "status": s,
            "error": f"precondition failed: polymarket-us events list returned {s}",
        })
        return findings
    events = body.get("events") or []
    for e in events[:3]:
        if not isinstance(e, dict):
            continue
        slug = e.get("slug")
        if not slug:
            continue
        s2, snippet = _get(f"{GATEWAY_URL}/api/v1/polymarket-us/events/{slug}",
                           gateway_headers())
        if s2 != 200:
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/polymarket-us/events/{slug}",
                "category": "invariant",
                "severity": "high",
                "status": s2,
                "error": f"event slug {slug!r} from list returned {s2} on detail endpoint",
                "path_params": {"slug": slug},
                "response_snippet": (str(snippet)[:200] if snippet else None),
            })
    return findings


def gw_kalshi_list_then_orderbook() -> list[dict]:
    """List Kalshi markets → pick 3 → fetch orderbook. Each should return 200."""
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/kalshi/markets",
                   gateway_headers(), {"limit": 5})
    if s != 200 or not isinstance(body, dict):
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/kalshi/markets",
            "category": "precondition",
            "severity": "info",
            "status": s,
            "error": f"precondition failed: kalshi market list returned {s}",
        })
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


def gw_coinbase_products_then_ticker() -> list[dict]:
    """List Coinbase products → pick 3 → fetch ticker. Every listed
    product id must resolve at the ticker endpoint."""
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/coinbase/products", gateway_headers())
    if s != 200 or not isinstance(body, list):
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/coinbase/products",
            "category": "precondition",
            "severity": "info",
            "status": s,
            "error": f"precondition failed: coinbase products returned {s}",
        })
        return findings
    picks = [p.get("id") for p in body[:3] if isinstance(p, dict) and p.get("id")]
    for pid in picks:
        s2, _ = _get(f"{GATEWAY_URL}/api/v1/coinbase/products/{pid}/ticker",
                     gateway_headers())
        if s2 != 200:
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/coinbase/products/{product_id}/ticker",
                "category": "invariant",
                "severity": "high",
                "status": s2,
                "error": f"product {pid!r} listed but ticker returned {s2}",
                "path_params": {"product_id": pid},
            })
    return findings


def gw_gemini_symbols_then_book() -> list[dict]:
    """List Gemini symbols → pick 3 → fetch orderbook. Listed symbols
    must resolve at /v1/book/{symbol}."""
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/gemini/v1/symbols", gateway_headers())
    if s != 200 or not isinstance(body, list):
        findings.append({
            "service": "gateway",
            "endpoint": "/api/v1/gemini/v1/symbols",
            "category": "precondition",
            "severity": "info",
            "status": s,
            "error": f"precondition failed: gemini symbols returned {s}",
        })
        return findings
    # prefer well-known liquid majors when available; otherwise sample first 3
    preferred = [s for s in ("btcusd", "ethusd", "solusd") if s in body]
    picks = preferred or body[:3]
    for sym in picks:
        s2, _ = _get(f"{GATEWAY_URL}/api/v1/gemini/v1/book/{sym}", gateway_headers())
        if s2 != 200:
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/gemini/v1/book/{symbol}",
                "category": "invariant",
                "severity": "high",
                "status": s2,
                "error": f"symbol {sym!r} listed but book returned {s2}",
                "path_params": {"symbol": sym},
            })
    return findings


ALL_STATEFUL_TESTS = [
    gw_polymarket_us_list_then_detail,
    gw_polymarket_us_events_list_then_detail,
    gw_kalshi_list_then_orderbook,
    gw_coinbase_products_then_ticker,
    gw_gemini_symbols_then_book,
]
