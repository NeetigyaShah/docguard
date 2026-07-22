"""Regression wrapper: every milestone scenario must PASS under pytest too.

The serial evidence run is `scripts/run_milestone.py`; this asserts the same
scenarios so they are part of the normal test suite. Extend PHASES as phases land.
"""

import importlib

import pytest

PHASES = [1, 2, 3, 4, 5, 6]

_cases = []
for _p in PHASES:
    try:
        _mod = importlib.import_module(f"tests.milestones.phase{_p}")
        _cases.extend(_mod.SCENARIOS)
    except ModuleNotFoundError:
        pass


@pytest.mark.parametrize("sc", _cases, ids=[c.id for c in _cases])
def test_milestone_scenario(sc):
    rec = sc.run()
    assert rec["status"] == "PASS", rec
