"""Milestone scenarios: run serially, recorded with input/expected/actual/PASS.

Each phase module exposes SCENARIOS: a list of Scenario. The runner
(scripts/run_milestone.py) executes them one at a time and writes evidence into
.orchestrator/tests.json; pytest (test_milestones.py) asserts the same set for
regression.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Scenario:
    id: str
    phase: int
    description: str
    input: str
    expected: Any
    fn: Callable[[], Any]
    kind: str = "predefined"  # predefined | orchestrator

    def run(self) -> dict:
        try:
            actual = self.fn()
            status = "PASS" if actual == self.expected else "FAIL"
        except Exception as e:  # evidence for failures
            actual, status = f"EXCEPTION: {e!r}", "FAIL"
        return {
            "id": self.id, "phase": self.phase, "kind": self.kind,
            "description": self.description, "input": self.input,
            "expected": repr(self.expected), "actual": repr(actual), "status": status,
        }
