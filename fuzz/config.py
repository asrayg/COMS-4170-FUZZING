"""Central configuration. Loads from .env if present, else environment."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
SPECS_DIR = ROOT / "specs"

# load .env at import time (no-op if missing)
load_dotenv(ROOT / ".env")

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

GATEWAY_URL = os.getenv("GRAYLAYER_GATEWAY_URL", "https://gateway.graylayer.tech").rstrip("/")
GATEWAY_KEY = os.getenv("GRAYLAYER_GATEWAY_API_KEY", "").strip()

MAX_EXAMPLES = int(os.getenv("FUZZ_MAX_EXAMPLES", "75"))
REQUEST_TIMEOUT = float(os.getenv("FUZZ_REQUEST_TIMEOUT", "15"))
RATE_LIMIT_SLEEP = float(os.getenv("FUZZ_RATE_LIMIT_SLEEP", "0.25"))
WORKERS = int(os.getenv("FUZZ_WORKERS", "1"))

SPEC_GATEWAY = SPECS_DIR / "market_proxy.yaml"


def gateway_headers() -> dict[str, str]:
    """Headers used for every gateway call. `X-API-Key` per docs."""
    h = {"Accept": "application/json", "User-Agent": "graylayer-fuzz/1.0"}
    if GATEWAY_KEY:
        h["X-API-Key"] = GATEWAY_KEY
    return h
