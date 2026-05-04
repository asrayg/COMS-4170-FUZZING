"""Generate paper figures from results/."""
import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

RESULTS = Path(__file__).resolve().parent.parent / "results"
OUT = RESULTS

JSONLS = {
    "Schemathesis": "gateway_findings.jsonl",
    "Negative":     "negative_findings.jsonl",
    "Differential": "differential_findings.jsonl",
    "Stateful":     "stateful_findings.jsonl",
}

def load(fn):
    p = RESULTS / fn
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out

all_events = {k: load(v) for k, v in JSONLS.items()}
flat = [(suite, e) for suite, evs in all_events.items() for e in evs]

# ── 1. Status code distribution ───────────────────────────────────────────
statuses = Counter()
for _, e in flat:
    s = e.get("status")
    if s is None:
        statuses["none"] += 1
    else:
        try:
            statuses[str(int(float(s)))] += 1
        except (TypeError, ValueError):
            statuses["none"] += 1

ordered = sorted(statuses.items(), key=lambda x: (x[0] == "none", x[0]))
labels = [k for k, _ in ordered]
vals   = [v for _, v in ordered]

fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(labels, vals, color="#3a6ea5")
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.01,
            str(v), ha="center", va="bottom", fontsize=9)
ax.set_xlabel("HTTP status")
ax.set_ylabel("Events")
ax.set_title("Response status distribution across all suites")
ax.set_yscale("log")
plt.tight_layout()
plt.savefig(OUT / "by_status.png", dpi=150)
plt.close()

# ── 2. Findings per suite ─────────────────────────────────────────────────
suite_totals = {k: len(v) for k, v in all_events.items()}
suite_high   = {k: sum(1 for e in v if e.get("severity") == "high")
                for k, v in all_events.items()}

fig, ax = plt.subplots(figsize=(7, 4))
xs = list(suite_totals.keys())
totals = [suite_totals[k] for k in xs]
highs  = [suite_high[k]   for k in xs]
x_pos = range(len(xs))
ax.bar(x_pos, totals, color="#3a6ea5", label="Total events")
ax.bar(x_pos, highs,  color="#c0392b", label="High severity")
for i, (t, h) in enumerate(zip(totals, highs)):
    ax.text(i, t + max(totals) * 0.01, str(t), ha="center", fontsize=9)
    if h > 0:
        ax.text(i, h + max(totals) * 0.01, str(h), ha="center",
                fontsize=8, color="#c0392b")
ax.set_xticks(list(x_pos))
ax.set_xticklabels(xs)
ax.set_ylabel("Events")
ax.set_title("Events recorded per test suite")
ax.legend()
plt.tight_layout()
plt.savefig(OUT / "by_suite.png", dpi=150)
plt.close()

# ── 3. Findings per venue ─────────────────────────────────────────────────
KNOWN = {"coinbase", "polymarket-us", "kalshi", "gemini", "forecastex"}
def venue(ep):
    parts = (ep or "").split("/")
    if len(parts) >= 4 and parts[1] == "api":
        v = parts[3]
        return v if v in KNOWN else "synthetic"
    return "synthetic"

venues = Counter()
venues_high = Counter()
for _, e in flat:
    v = venue(e.get("endpoint", ""))
    venues[v] += 1
    if e.get("severity") == "high":
        venues_high[v] += 1

ordered_v = sorted(venues.items(), key=lambda x: -x[1])
labs = [k for k, _ in ordered_v]
vals = [v for _, v in ordered_v]
high_vals = [venues_high[k] for k in labs]

fig, ax = plt.subplots(figsize=(7.5, 4))
x_pos = range(len(labs))
ax.bar(x_pos, vals, color="#3a6ea5", label="All events")
ax.bar(x_pos, high_vals, color="#c0392b", label="High severity")
for i, (t, h) in enumerate(zip(vals, high_vals)):
    ax.text(i, t + max(vals) * 0.01, str(t), ha="center", fontsize=9)
ax.set_xticks(list(x_pos))
ax.set_xticklabels(labs, rotation=20, ha="right")
ax.set_ylabel("Events")
ax.set_title("Events by upstream venue")
ax.legend()
plt.tight_layout()
plt.savefig(OUT / "by_venue.png", dpi=150)
plt.close()

# ── 4. High-severity by endpoint ──────────────────────────────────────────
high_eps = Counter()
for _, e in flat:
    if e.get("severity") == "high":
        high_eps[e.get("endpoint", "?")] += 1

ordered_h = sorted(high_eps.items(), key=lambda x: x[1])
labs = [k for k, _ in ordered_h]
vals = [v for _, v in ordered_h]

fig, ax = plt.subplots(figsize=(8, 4.5))
y_pos = range(len(labs))
ax.barh(list(y_pos), vals, color="#c0392b")
for i, v in enumerate(vals):
    ax.text(v + 0.05, i, str(v), va="center", fontsize=9)
ax.set_yticks(list(y_pos))
ax.set_yticklabels(labs, fontsize=8)
ax.set_xlabel("High-severity findings")
ax.set_title("High-severity findings by endpoint")
plt.tight_layout()
plt.savefig(OUT / "high_by_endpoint.png", dpi=150)
plt.close()

print("wrote:", "by_status.png", "by_suite.png", "by_venue.png",
      "high_by_endpoint.png")
