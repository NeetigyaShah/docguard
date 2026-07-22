"""Minimal orchestrator-state helpers: append audit activity, record test evidence.

Usage:
  python scripts/orch.py log <actor> <feature> <action> <result> [--commit SHA]
  python scripts/orch.py add-tests <path-to-json-array>   # merge records into tests.json
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ORCH = Path(__file__).resolve().parent.parent / ".orchestrator"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(actor: str, feature: str, action: str, result: str, commit: str = "") -> None:
    rec = {
        "ts": _now(), "actor": actor, "feature": feature,
        "action": action, "result": result, "commit": commit,
    }
    with (ORCH / "activity.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def add_tests(records: list[dict]) -> None:
    path = ORCH / "tests.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"records": []}
    data["records"].extend(records)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]
    if cmd == "log":
        commit = ""
        if "--commit" in rest:
            i = rest.index("--commit")
            commit = rest[i + 1]
            rest = rest[:i]
        actor, feature, action, result = (rest + ["", "", "", ""])[:4]
        log(actor, feature, action, result, commit)
        return 0
    if cmd == "add-tests":
        add_tests(json.loads(Path(rest[0]).read_text(encoding="utf-8")))
        return 0
    print(f"unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
