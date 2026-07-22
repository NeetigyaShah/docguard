"""Run a phase's milestone scenarios SERIALLY, print evidence, record to tests.json.

Usage: python scripts/run_milestone.py <phase-int>
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.orch import add_tests, log  # noqa: E402


def main(phase: int) -> int:
    mod = importlib.import_module(f"tests.milestones.phase{phase}")
    scenarios = mod.SCENARIOS
    records, passed = [], 0
    print(f"\n=== PHASE {phase} MILESTONE — {len(scenarios)} scenarios (serial) ===\n")
    for sc in scenarios:
        rec = sc.run()
        records.append(rec)
        if rec["status"] == "PASS":
            passed += 1
        mark = "PASS" if rec["status"] == "PASS" else "**FAIL**"
        print(f"[{rec['id']}] ({rec['kind']}) {rec['description']}")
        print(f"    input:    {rec['input']}")
        print(f"    expected: {rec['expected']}")
        print(f"    actual:   {rec['actual']}")
        print(f"    -> {mark}\n")
    add_tests(records)
    log("orchestrator", f"phase-{phase}", f"milestone suite ({len(scenarios)} serial)",
        f"{passed}/{len(scenarios)} PASS")
    print(f"=== PHASE {phase}: {passed}/{len(scenarios)} PASS ===")
    # persist a compact summary for the dashboard milestone counts
    return 0 if passed == len(scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1])))
