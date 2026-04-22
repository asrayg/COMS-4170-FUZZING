"""Failure and event collection.

Design goals:
- Append-only JSONL so runs are never lost if a process dies mid-way.
- A consolidated JSON snapshot at the end for human + pandas reading.
- A markdown summary grouping by endpoint and failure class.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import RESULTS_DIR

_lock = threading.Lock()


@dataclass
class Finding:
    """One fuzz finding. `severity` is populated by classifier below."""
    service: str              # "gateway" | "data"
    endpoint: str             # path template, e.g. /api/v1/kalshi/markets
    method: str               # GET, POST, ...
    status: int | None        # HTTP status (None if request raised)
    category: str             # crash | contract | timeout | transport | unexpected_status | invariant
    severity: str = "info"    # info | low | medium | high
    query: dict[str, Any] | None = None
    path_params: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    request_body: Any | None = None
    response_snippet: str | None = None
    error: str | None = None
    elapsed_ms: float | None = None
    ts: float = field(default_factory=time.time)


class Reporter:
    """Thread-safe sink for findings."""

    def __init__(self, name: str):
        self.name = name
        self.jsonl_path = RESULTS_DIR / f"{name}.jsonl"
        self.json_path = RESULTS_DIR / f"{name}.json"
        # reset files at start of run so each run is self-contained
        self.jsonl_path.write_text("", encoding="utf-8")
        self._items: list[Finding] = []

    def record(self, f: Finding) -> None:
        with _lock:
            self._items.append(f)
            with self.jsonl_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(asdict(f), default=str) + "\n")

    def flush(self) -> None:
        with _lock:
            payload = [asdict(x) for x in self._items]
        self.json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._items)


def classify(status: int | None, error: str | None) -> tuple[str, str]:
    """Return (category, severity) for a response."""
    if error:
        if "timeout" in error.lower():
            return "timeout", "medium"
        if "connection" in error.lower() or "ssl" in error.lower():
            return "transport", "medium"
        # schemathesis validation errors land here
        if "validation" in error.lower() or "schema" in error.lower():
            return "contract", "high"
        return "unexpected", "medium"
    if status is None:
        return "unknown", "low"
    if status >= 500:
        # 502/503 are documented upstream-failure codes → low severity
        if status in (502, 503):
            return "upstream", "low"
        return "crash", "high"  # 500, 504, etc. indicate a server bug
    if status == 429:
        return "rate_limit", "info"
    if 400 <= status < 500:
        return "client_error", "info"
    return "ok", "info"
