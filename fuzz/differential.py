"""Differential / invariant tests.

These run *after* fuzzing with real inputs and check *semantic* properties
that OpenAPI alone cannot express. They're cheap, deterministic, and give
you killer findings to cite in the paper.

Each test function returns a list of Finding-like dicts. A test harness in
tests/test_differential.py drives them.
"""
from __future__ import annotations

from typing import Any

import requests

from .config import DATA_URL, GATEWAY_URL, REQUEST_TIMEOUT, data_headers, gateway_headers


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


# ────────────────────────────────────────────────────────────────────────────
# Gateway (Market Proxy) invariants
# ────────────────────────────────────────────────────────────────────────────

def gw_midpoint_between_best_prices() -> list[dict]:
    """CLOB midpoint must satisfy best_bid <= midpoint <= best_ask."""
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/polymarket-clob/markets", gateway_headers())
    if s != 200 or not isinstance(body, (list, dict)):
        return findings
    markets = body if isinstance(body, list) else body.get("data", [])
    # pick up to 5 active-looking markets and sample one token each
    sampled = 0
    for m in markets:
        if sampled >= 5:
            break
        tokens = m.get("tokens") if isinstance(m, dict) else None
        if not tokens:
            continue
        token_id = tokens[0].get("token_id") if isinstance(tokens[0], dict) else None
        if not token_id:
            continue
        sampled += 1
        # fetch book + midpoint
        _, book = _get(f"{GATEWAY_URL}/api/v1/polymarket-clob/book",
                       gateway_headers(), {"token_id": token_id})
        _, mid = _get(f"{GATEWAY_URL}/api/v1/polymarket-clob/midpoint",
                      gateway_headers(), {"token_id": token_id})
        if not isinstance(book, dict) or not isinstance(mid, dict):
            continue
        try:
            best_bid = max(float(b["price"]) for b in book.get("bids", []) or [])
            best_ask = min(float(a["price"]) for a in book.get("asks", []) or [])
            m_val = float(mid.get("mid") or mid.get("midpoint") or mid.get("price"))
        except (TypeError, ValueError, KeyError):
            continue
        if not (best_bid - 1e-9 <= m_val <= best_ask + 1e-9):
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/polymarket-clob/midpoint",
                "category": "invariant",
                "severity": "high",
                "error": f"midpoint {m_val} outside [{best_bid}, {best_ask}]",
                "path_params": {"token_id": token_id},
            })
    return findings


def gw_spread_nonnegative() -> list[dict]:
    """CLOB spread must be >= 0."""
    findings: list[dict] = []
    s, body = _get(f"{GATEWAY_URL}/api/v1/polymarket-clob/markets", gateway_headers())
    if s != 200:
        return findings
    markets = body if isinstance(body, list) else body.get("data", []) if isinstance(body, dict) else []
    checked = 0
    for m in markets[:20]:
        tokens = m.get("tokens") if isinstance(m, dict) else None
        if not tokens:
            continue
        token_id = tokens[0].get("token_id") if isinstance(tokens[0], dict) else None
        if not token_id:
            continue
        checked += 1
        _, spr = _get(f"{GATEWAY_URL}/api/v1/polymarket-clob/spread",
                      gateway_headers(), {"token_id": token_id})
        if isinstance(spr, dict):
            try:
                val = float(spr.get("spread"))
            except (TypeError, ValueError):
                continue
            if val < 0:
                findings.append({
                    "service": "gateway",
                    "endpoint": "/api/v1/polymarket-clob/spread",
                    "category": "invariant",
                    "severity": "high",
                    "error": f"negative spread {val}",
                    "path_params": {"token_id": token_id},
                })
        if checked >= 10:
            break
    return findings


def gw_pagination_monotone() -> list[dict]:
    """Two pages of /polymarket/markets with different offsets should not
    return *exactly* the same set — detects broken pagination."""
    findings: list[dict] = []
    s1, p1 = _get(f"{GATEWAY_URL}/api/v1/polymarket/markets",
                  gateway_headers(), {"limit": 5, "offset": 0})
    s2, p2 = _get(f"{GATEWAY_URL}/api/v1/polymarket/markets",
                  gateway_headers(), {"limit": 5, "offset": 5})
    if s1 == 200 and s2 == 200 and isinstance(p1, list) and isinstance(p2, list):
        ids1 = {m.get("id") for m in p1 if isinstance(m, dict)}
        ids2 = {m.get("id") for m in p2 if isinstance(m, dict)}
        if ids1 and ids2 and ids1 == ids2:
            findings.append({
                "service": "gateway",
                "endpoint": "/api/v1/polymarket/markets",
                "category": "invariant",
                "severity": "medium",
                "error": "offset=0 and offset=5 returned identical market ids",
            })
    return findings


def gw_auth_gate_consistency() -> list[dict]:
    """Endpoints that require auth must return 401 when no key is supplied.

    Health is exempt. Coinbase endpoints are documented public.
    """
    findings: list[dict] = []
    probes = [
        "/api/v1/polymarket/markets",
        "/api/v1/kalshi/markets",
        "/api/v1/gemini/v2/ticker/BTCUSD",
        "/api/v1/forecastex/contracts",
    ]
    headers = {"Accept": "application/json"}  # no X-API-Key
    for p in probes:
        s, _ = _get(f"{GATEWAY_URL}{p}", headers)
        if s == 0:
            continue
        if s != 401:
            findings.append({
                "service": "gateway",
                "endpoint": p,
                "category": "invariant",
                "severity": "medium",
                "status": s,
                "error": f"expected 401 without API key, got {s}",
            })
    return findings


# ────────────────────────────────────────────────────────────────────────────
# Orderbook History invariants
# ────────────────────────────────────────────────────────────────────────────

def data_snapshot_ordering() -> list[dict]:
    """Snapshot rows must be sorted by ts ascending per docs."""
    findings: list[dict] = []
    for exch in ("kalshi", "polymarket_us", "gemini"):
        _, tickers = _get(f"{DATA_URL}/api/{exch}/tickers", data_headers())
        if not isinstance(tickers, dict):
            continue
        items = tickers.get("tickers") or []
        if not items:
            continue
        sample = items[0]
        _, body = _get(f"{DATA_URL}/api/{exch}/snapshots/{sample}",
                       data_headers(), {"limit": 200})
        if not isinstance(body, dict):
            continue
        rows = body.get("rows") or []
        tss = [r.get("ts") for r in rows if isinstance(r, dict) and r.get("ts")]
        if tss != sorted(tss):
            findings.append({
                "service": "data",
                "endpoint": f"/api/{exch}/snapshots/{{ticker}}",
                "category": "invariant",
                "severity": "high",
                "error": "rows not sorted by ts ascending",
                "path_params": {"ticker": sample},
            })
    return findings


def data_delta_sequence_monotone() -> list[dict]:
    """Within a single ts, delta sequence numbers should be strictly increasing."""
    findings: list[dict] = []
    for exch in ("kalshi", "polymarket_us", "gemini"):
        _, tickers = _get(f"{DATA_URL}/api/{exch}/tickers", data_headers())
        if not isinstance(tickers, dict):
            continue
        items = tickers.get("tickers") or []
        if not items:
            continue
        sample = items[0]
        _, body = _get(f"{DATA_URL}/api/{exch}/deltas/{sample}",
                       data_headers(), {"limit": 500})
        if not isinstance(body, dict):
            continue
        rows = body.get("rows") or []
        # check strict monotonicity overall (sequence is exchange-wide, not per-ts)
        seqs = [r.get("sequence") for r in rows if isinstance(r, dict)]
        seqs = [s for s in seqs if isinstance(s, int)]
        for a, b in zip(seqs, seqs[1:]):
            if b < a:
                findings.append({
                    "service": "data",
                    "endpoint": f"/api/{exch}/deltas/{{ticker}}",
                    "category": "invariant",
                    "severity": "medium",
                    "error": f"non-monotone sequence: {a} -> {b}",
                    "path_params": {"ticker": sample},
                })
                break
    return findings


def data_count_matches_rows() -> list[dict]:
    """Response `count` should equal len(rows)."""
    findings: list[dict] = []
    for exch in ("kalshi", "polymarket_us", "gemini"):
        _, tickers = _get(f"{DATA_URL}/api/{exch}/tickers", data_headers())
        if not isinstance(tickers, dict):
            continue
        items = tickers.get("tickers") or []
        if not items:
            continue
        sample = items[0]
        for kind in ("snapshots", "deltas"):
            _, body = _get(f"{DATA_URL}/api/{exch}/{kind}/{sample}",
                           data_headers(), {"limit": 50})
            if not isinstance(body, dict):
                continue
            c = body.get("count")
            rows = body.get("rows") or []
            if isinstance(c, int) and c != len(rows):
                findings.append({
                    "service": "data",
                    "endpoint": f"/api/{exch}/{kind}/{{ticker}}",
                    "category": "invariant",
                    "severity": "medium",
                    "error": f"count={c} but rows has {len(rows)} entries",
                    "path_params": {"ticker": sample},
                })
    return findings


def data_anon_history_clamp() -> list[dict]:
    """Docs say anonymous requests are clamped to the last 1 day. Verify.

    We send an anonymous request with start_ts set to 30 days ago and check
    that no returned row has ts older than ~1 day.
    """
    findings: list[dict] = []
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    old = (now - dt.timedelta(days=30)).isoformat().replace("+00:00", "Z")
    cutoff = now - dt.timedelta(days=1, hours=1)  # 1h grace

    headers = {"Accept": "application/json"}  # no key
    s, tickers = _get(f"{DATA_URL}/api/kalshi/tickers", headers)
    if s != 200 or not isinstance(tickers, dict):
        return findings
    items = tickers.get("tickers") or []
    if not items:
        return findings
    sample = items[0]
    s, body = _get(f"{DATA_URL}/api/kalshi/snapshots/{sample}",
                   headers, {"start_ts": old, "limit": 50})
    if s != 200 or not isinstance(body, dict):
        return findings
    for r in body.get("rows", []):
        ts = r.get("ts")
        if not ts:
            continue
        try:
            parsed = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed < cutoff:
            findings.append({
                "service": "data",
                "endpoint": "/api/kalshi/snapshots/{ticker}",
                "category": "invariant",
                "severity": "high",
                "error": f"anonymous request returned row older than 1 day: {ts}",
                "path_params": {"ticker": sample},
            })
            break
    return findings


ALL_DIFFERENTIAL_TESTS = [
    gw_midpoint_between_best_prices,
    gw_spread_nonnegative,
    gw_pagination_monotone,
    gw_auth_gate_consistency,
    data_snapshot_ordering,
    data_delta_sequence_monotone,
    data_count_matches_rows,
    data_anon_history_clamp,
]
