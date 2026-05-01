"""Hand-crafted malformed inputs ("negative tests").

Schemathesis generates *valid* inputs by default and can also do "negative"
data generation, but having a curated list of known-nasty payloads gives
the paper concrete, reproducible cases to cite. These hit classic categories:

- Type confusion (string where int expected, etc.)
- Boundary values (min-1, max+1, 0, negative, huge)
- Encoding issues (unicode, nulls, traversal)
- Injection surfaces (SQL/NoSQL/SSRF payloads)
- Protocol abuse (oversized query strings)

These are executed as plain pytest tests via `tests/test_negative.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

BIG_INT = 2**63
HUGE_STRING = "A" * 10_000


@dataclass(frozen=True)
class NegativeCase:
    name: str
    service: str              # always "gateway"
    path: str                 # fully-qualified path to hit (base-URL appended at runtime)
    params: dict | None = None
    expected_statuses: tuple[int, ...] = (400, 404, 422)  # acceptable rejections
    note: str = ""


GATEWAY_NEGATIVES: list[NegativeCase] = [
    # ── Coinbase ─────────────────────────────────────────────────
    NegativeCase(
        "coinbase_product_with_traversal",
        "gateway",
        "/api/v1/coinbase/products/..%2F..%2Fetc%2Fpasswd",
        note="path traversal attempt in path param",
    ),
    NegativeCase(
        "coinbase_product_with_null_byte",
        "gateway",
        "/api/v1/coinbase/products/BTC-USD%00",
        note="null-byte injection in path param",
    ),
    NegativeCase(
        "coinbase_candles_wrong_type_granularity",
        "gateway",
        "/api/v1/coinbase/products/BTC-USD/candles",
        params={"granularity": "banana"},
        note="string where integer enum expected",
    ),
    NegativeCase(
        "coinbase_candles_inverted_window",
        "gateway",
        "/api/v1/coinbase/products/BTC-USD/candles",
        params={"start": "2030-01-01T00:00:00Z", "end": "2020-01-01T00:00:00Z"},
        expected_statuses=(200, 400),  # some APIs accept; some reject
        note="end < start (semantic)",
    ),
    NegativeCase(
        "coinbase_candles_bad_iso",
        "gateway",
        "/api/v1/coinbase/products/BTC-USD/candles",
        params={"start": "not-a-date"},
        note="malformed date-time",
    ),

    # ── Polymarket Gamma ─────────────────────────────────────────
    NegativeCase(
        "polymarket_limit_too_large",
        "gateway",
        "/api/v1/polymarket-us/markets",
        params={"limit": 1_000_000},
        expected_statuses=(200, 400, 422),
        note="limit far above documented max of 500",
    ),
    NegativeCase(
        "polymarket_limit_negative",
        "gateway",
        "/api/v1/polymarket-us/markets",
        params={"limit": -5},
        note="negative limit (documented minimum is 1)",
    ),
    NegativeCase(
        "polymarket_offset_huge",
        "gateway",
        "/api/v1/polymarket-us/markets",
        params={"offset": BIG_INT},
        expected_statuses=(200, 400, 422),
        note="offset beyond int64",
    ),
    NegativeCase(
        "polymarket_active_not_boolean",
        "gateway",
        "/api/v1/polymarket-us/markets",
        params={"active": "maybe"},
        note="non-boolean where boolean expected",
    ),
    NegativeCase(
        "polymarket_search_missing_q",
        "gateway",
        "/api/v1/polymarket-us/search",
        note="required query parameter omitted",
    ),
    NegativeCase(
        "polymarket_search_oversize_q",
        "gateway",
        "/api/v1/polymarket-us/search",
        params={"q": HUGE_STRING},
        expected_statuses=(200, 400, 414, 422),
        note="query string far above documented 200 char max",
    ),

    # ── Kalshi ───────────────────────────────────────────────────
    NegativeCase(
        "kalshi_status_typo",
        "gateway",
        "/api/v1/kalshi/markets",
        params={"status": "clsd"},
        note="typo in status enum",
    ),
    NegativeCase(
        "kalshi_limit_overflow",
        "gateway",
        "/api/v1/kalshi/markets",
        params={"limit": 99_999},
        expected_statuses=(200, 400, 422),
        note="limit above documented max of 1000",
    ),
    NegativeCase(
        "kalshi_close_ts_inverted",
        "gateway",
        "/api/v1/kalshi/markets",
        params={"min_close_ts": 2_000_000_000, "max_close_ts": 100},
        expected_statuses=(200, 400),
        note="min > max (semantic)",
    ),

    # ── Gemini ───────────────────────────────────────────────────
    NegativeCase(
        "gemini_book_unknown_symbol",
        "gateway",
        "/api/v1/gemini/v1/book/ZZZZZZZZ",
        expected_statuses=(200, 400, 404),
        note="non-existent symbol",
    ),
    NegativeCase(
        "gemini_trades_limit_wrong_type",
        "gateway",
        "/api/v1/gemini/v1/trades/BTCUSD",
        params={"limit_trades": "many"},
        note="string where integer expected",
    ),

    # ── Forecastex ───────────────────────────────────────────────
    NegativeCase(
        "forecastex_sort_order_bad",
        "gateway",
        "/api/v1/forecastex/contracts",
        params={"sortOrder": "upward"},
        note="sortOrder outside enum",
    ),
    NegativeCase(
        "forecastex_page_size_overflow",
        "gateway",
        "/api/v1/forecastex/contracts",
        params={"pageSize": 10_000},
        expected_statuses=(200, 400, 422),
        note="pageSize far above documented max of 100",
    ),

    # ── Generic ──────────────────────────────────────────────────
    NegativeCase(
        "unknown_endpoint",
        "gateway",
        "/api/v1/does/not/exist",
        expected_statuses=(404,),
        note="sanity check: unknown route",
    ),

    # ── SQL injection ─────────────────────────────────────────────
    NegativeCase(
        "sqli_polymarket_search",
        "gateway",
        "/api/v1/polymarket-us/search",
        params={"q": "' OR 1=1 --"},
        expected_statuses=(200, 400, 422),
        note="SQL injection in search query",
    ),
    NegativeCase(
        "sqli_kalshi_status",
        "gateway",
        "/api/v1/kalshi/markets",
        params={"status": "open'; DROP TABLE markets;--"},
        expected_statuses=(200, 400, 422),
        note="SQL injection in status param",
    ),

    # ── NoSQL injection ───────────────────────────────────────────
    NegativeCase(
        "nosqli_polymarket_id",
        "gateway",
        "/api/v1/polymarket-us/markets/%7B%22%24gt%22%3A%22%22%7D",
        expected_statuses=(400, 404, 422, 500),
        note="NoSQL $gt operator in path param",
    ),
    NegativeCase(
        "nosqli_search_regex",
        "gateway",
        "/api/v1/polymarket-us/search",
        params={"q": '{"$regex": ".*"}'},
        expected_statuses=(200, 400, 422),
        note="NoSQL $regex injection in query",
    ),

    # ── SSRF probes ───────────────────────────────────────────────
    NegativeCase(
        "ssrf_coinbase_product_localhost",
        "gateway",
        "/api/v1/coinbase/products/http%3A%2F%2F127.0.0.1%3A80",
        expected_statuses=(400, 404, 422),
        note="SSRF probe: localhost URL in path param",
    ),
    NegativeCase(
        "ssrf_gemini_symbol_internal",
        "gateway",
        "/api/v1/gemini/v1/book/http%3A%2F%2F169.254.169.254%2Flatest%2Fmeta-data",
        expected_statuses=(400, 404, 422),
        note="SSRF probe: AWS metadata endpoint in path param",
    ),

    # ── Unicode / encoding edge cases ─────────────────────────────
    NegativeCase(
        "unicode_bom_search",
        "gateway",
        "/api/v1/polymarket-us/search",
        params={"q": "\ufeffbitcoin"},
        expected_statuses=(200, 400, 422),
        note="BOM character prefixed to query",
    ),
    NegativeCase(
        "unicode_rtl_override",
        "gateway",
        "/api/v1/polymarket-us/search",
        params={"q": "\u202ebitcoin"},
        expected_statuses=(200, 400, 422),
        note="RTL override character in query",
    ),
    NegativeCase(
        "unicode_null_in_query",
        "gateway",
        "/api/v1/polymarket-us/search",
        params={"q": "bit\x00coin"},
        expected_statuses=(200, 400, 422),
        note="embedded null byte in query string",
    ),
]
