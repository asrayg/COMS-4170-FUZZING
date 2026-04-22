"""Aggregate findings into summary.md, summary.csv, and two plots.

Reads every *_findings.jsonl in results/, produces:
  results/summary.md     — paper-ready tables
  results/summary.csv    — full flat table
  results/by_endpoint.png
  results/by_severity.png
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

try:
    import pandas as pd
except Exception as e:  # noqa: BLE001
    print(f"pandas import failed: {e}", file=sys.stderr)
    sys.exit(1)


def load_findings() -> pd.DataFrame:
    rows: list[dict] = []
    for p in RESULTS.glob("*_findings.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(rows)


def main() -> int:
    df = load_findings()
    if df.empty:
        (RESULTS / "summary.md").write_text(
            "# Fuzzing Summary\n\nNo findings recorded. Did the test run complete?\n",
            encoding="utf-8",
        )
        print("No findings found. Wrote placeholder summary.md.")
        return 0

    # Normalize columns that may be missing
    for col in ("service", "endpoint", "method", "status", "category", "severity"):
        if col not in df.columns:
            df[col] = None

    df.to_csv(RESULTS / "summary.csv", index=False)

    total = len(df)
    by_service = df.groupby("service").size().sort_values(ascending=False)
    by_severity = df.groupby("severity").size().sort_values(ascending=False)
    by_category = df.groupby("category").size().sort_values(ascending=False)

    # Findings per endpoint, split by severity (focus on non-ok)
    non_ok = df[~df["category"].isin(["ok"])].copy() if "category" in df else df
    by_endpoint = (
        non_ok.groupby(["service", "endpoint", "severity"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    # Status code histogram
    by_status = df["status"].value_counts(dropna=False).sort_index()

    # High-severity drill-down (the stars of the report)
    high = df[df["severity"].isin(["high"])].copy()
    high_table = (
        high.groupby(["service", "endpoint", "category"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    # ── Markdown ──
    md: list[str] = []
    md.append("# Graylayer Fuzzing — Results Summary")
    md.append("")
    md.append(f"- Total recorded events: **{total:,}**")
    md.append(f"- Services exercised: **{', '.join(sorted(df['service'].dropna().unique()))}**")
    md.append(f"- Unique endpoints exercised: **{df['endpoint'].nunique()}**")
    md.append("")

    md.append("## Events by service")
    md.append(by_service.to_frame("events").to_markdown())
    md.append("")
    md.append("## Events by severity")
    md.append(by_severity.to_frame("events").to_markdown())
    md.append("")
    md.append("## Events by category")
    md.append(by_category.to_frame("events").to_markdown())
    md.append("")
    md.append("## Status code distribution")
    md.append(by_status.to_frame("events").to_markdown())
    md.append("")

    md.append("## High-severity findings by endpoint")
    if high_table.empty:
        md.append("_No high-severity findings recorded._")
    else:
        md.append(high_table.to_markdown(index=False))
    md.append("")

    md.append("## Top 20 non-OK endpoints")
    md.append(by_endpoint.head(20).to_markdown(index=False))
    md.append("")

    # Sample a few concrete high-severity cases verbatim
    md.append("## Representative high-severity cases (first 5)")
    cols = ["service", "endpoint", "method", "status", "category", "error", "query", "path_params"]
    avail = [c for c in cols if c in high.columns]
    samples = high[avail].head(5)
    if samples.empty:
        md.append("_None._")
    else:
        md.append(samples.to_markdown(index=False))
    md.append("")

    (RESULTS / "summary.md").write_text("\n".join(md), encoding="utf-8")

    # ── Plots ──
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # By endpoint (top 15)
        top = by_endpoint.head(15).copy()
        if not top.empty:
            top["label"] = top["service"] + ":" + top["endpoint"].str[-40:]
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(top["label"][::-1], top["count"][::-1])
            ax.set_xlabel("Non-OK events")
            ax.set_title("Top endpoints by non-OK fuzz events")
            fig.tight_layout()
            fig.savefig(RESULTS / "by_endpoint.png", dpi=150)
            plt.close(fig)

        # By severity
        if not by_severity.empty:
            fig, ax = plt.subplots(figsize=(6, 4))
            by_severity.plot(kind="bar", ax=ax)
            ax.set_ylabel("Events")
            ax.set_title("Findings by severity")
            fig.tight_layout()
            fig.savefig(RESULTS / "by_severity.png", dpi=150)
            plt.close(fig)
    except Exception as e:  # noqa: BLE001
        print(f"plotting skipped: {e}", file=sys.stderr)

    print(f"Wrote {RESULTS / 'summary.md'}")
    print(f"Wrote {RESULTS / 'summary.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
