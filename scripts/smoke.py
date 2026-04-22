"""Sanity checks that run in seconds — no network traffic.

Use this to catch stupid bugs (bad YAML, import errors) before committing
to a full fuzz run.

    python scripts/smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_specs_parse() -> None:
    import yaml
    for spec in (ROOT / "specs").glob("*.yaml"):
        with spec.open() as fp:
            data = yaml.safe_load(fp)
        assert "paths" in data, f"{spec}: no paths"
        assert len(data["paths"]) > 0, f"{spec}: empty paths"
        print(f"  ok: {spec.name}  ({len(data['paths'])} paths)")


def check_schemathesis_loads() -> None:
    import schemathesis
    for spec in (ROOT / "specs").glob("*.yaml"):
        s = schemathesis.openapi.from_path(str(spec))
        ops = sum(1 for _ in s.get_all_operations())
        print(f"  ok: {spec.name}  ({ops} operations)")


def check_imports() -> None:
    from fuzz import config, differential, hooks, negatives, reporting, stateful  # noqa: F401
    print("  ok: fuzz.config, .hooks, .reporting, .negatives, .differential, .stateful")


def check_test_collection() -> None:
    import subprocess
    r = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise RuntimeError("pytest --collect-only failed")
    # last non-empty line of stdout is usually "<n> tests collected"
    last = [line for line in r.stdout.strip().splitlines() if line][-1] if r.stdout.strip() else ""
    print(f"  ok: {last}")


def main() -> int:
    print("1/4 yaml parse ....")
    check_specs_parse()
    print("2/4 schemathesis load ....")
    check_schemathesis_loads()
    print("3/4 python imports ....")
    check_imports()
    print("4/4 pytest collection ....")
    check_test_collection()
    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"\nSMOKE FAILED: {e}", file=sys.stderr)
        sys.exit(1)
