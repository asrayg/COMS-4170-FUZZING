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
    service: str              # "gateway" | "data"
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
        "/api/v1/polymarket/markets",
        params={"limit": 1_000_000},
        expected_statuses=(200, 400, 422),
        note="limit far above documented max of 500",
    ),
    NegativeCase(
        "polymarket_limit_negative",
        "gateway",
        "/api/v1/polymarket/markets",
        params={"limit": -5},
        note="negative limit (documented minimum is 1)",
    ),
    NegativeCase(
        "polymarket_offset_huge",
        "gateway",
        "/api/v1/polymarket/markets",
        params={"offset": BIG_INT},
        expected_statuses=(200, 400, 422),
        note="offset beyond int64",
    ),
    NegativeCase(
        "polymarket_active_not_boolean",
        "gateway",
        "/api/v1/polymarket/markets",
        params={"active": "maybe"},
        note="non-boolean where boolean expected",
    ),
    NegativeCase(
        "polymarket_search_missing_q",
        "gateway",
        "/api/v1/polymarket/search",
        note="required query parameter omitted",
    ),
    NegativeCase(
        "polymarket_search_oversize_q",
        "gateway",
        "/api/v1/polymarket/search",
        params={"q": HUGE_STRING},
        expected_statuses=(200, 400, 414, 422),
        note="query string far above documented 200 char max",
    ),

    # ── CLOB ─────────────────────────────────────────────────────
    NegativeCase(
        "clob_price_bad_side",
        "gateway",
        "/api/v1/polymarket-clob/price",
        params={"token_id": "0xdeadbeef", "side": "HODL"},
        note="side outside enum (BUY/SELL)",
    ),
    NegativeCase(
        "clob_missing_token_id",
        "gateway",
        "/api/v1/polymarket-clob/book",
        note="required token_id missing",
    ),
    NegativeCase(
        "clob_prices_history_bad_interval",
        "gateway",
        "/api/v1/polymarket-clob/prices-history",
        params={"token_id": "0x1", "interval": "42h"},
        note="interval outside enum",
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
]


DATA_NEGATIVES: list[NegativeCase] = [
    NegativeCase(
        "data_unknown_exchange",
        "data",
        "/api/bitmex/tickers",
        expected_statuses=(400, 404),
        note="exchange outside enum",
    ),
    NegativeCase(
        "data_snapshots_bad_ts",
        "data",
        "/api/kalshi/snapshots/KXBTC-25",
        params={"start_ts": "definitely-not-rfc3339"},
        note="malformed RFC 3339",
    ),
    NegativeCase(
        "data_snapshots_inverted_window",
        "data",
        "/api/kalshi/snapshots/KXBTC-25",
        params={"start_ts": "2030-01-01T00:00:00Z", "end_ts": "2020-01-01T00:00:00Z"},
        expected_statuses=(200, 400),
        note="end before start — should return empty 200 or 400",
    ),
    NegativeCase(
        "data_snapshots_way_before_history",
        "data",
        "/api/kalshi/snapshots/KXBTC-25",
        params={"start_ts": "1999-01-01T00:00:00Z", "limit": 10},
        expected_statuses=(200,),
        note="documented: start_ts clamps to earliest available",
    ),
    NegativeCase(
        "data_tickers_oversize_prefix",
        "data",
        "/api/kalshi/tickers",
        params={"prefix": HUGE_STRING},
        expected_statuses=(200, 400, 414),
        note="very long prefix",
    ),
    NegativeCase(
        "data_ticker_with_special_chars",
        "data",
        "/api/kalshi/snapshots/%00%00%00",
        expected_statuses=(200, 400, 404),
        note="null bytes in ticker path component",
    ),
    NegativeCase(
        "data_limit_negative",
        "data",
        "/api/kalshi/snapshots/KXBTC-25",
        params={"limit": -1},
        note="negative limit",
    ),
    NegativeCase(
        "data_limit_overflow",
        "data",
        "/api/kalshi/snapshots/KXBTC-25",
        params={"limit": 10_000_000},
        expected_statuses=(200, 400, 422),
        note="limit far above documented max",
    ),
    NegativeCase(
        "data_anon_old_data_clamp",
        "data",
        "/api/kalshi/deltas/KXBTC-25",
        params={"start_ts": "2026-03-08T00:00:00Z", "limit": 1},
        expected_statuses=(200, 401),
        note="docs say anon access is clamped to last 1 day; verify clamp happens",
    ),
]
