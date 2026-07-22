"""Phase 6 milestone scenarios: full E2E over real git repos + measured metrics."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.milestones import Scenario

from docguard.config import load_settings
from docguard.demo import API_MD, USERS_PY, compute_metrics
from docguard.models import Action, PipelineResult, StalenessLabel
from docguard.pipeline import analyze

_REMOVE_METHOD = '''

    def remove_member(self, name: str) -> None:
        """Remove a member by name."""
        self._members = [m for m in getattr(self, "_members", []) if m["name"] != name]'''


def _analyze_after(edit, *, base="HEAD~1", users=USERS_PY, docs=API_MD) -> PipelineResult:
    d = Path(tempfile.mkdtemp(prefix="docguard_p6_"))
    try:
        (d / "src").mkdir()
        (d / "docs").mkdir()
        (d / "src" / "users.py").write_text(users, encoding="utf-8")
        (d / "docs" / "api.md").write_text(docs, encoding="utf-8")

        def g(*a):
            subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)

        g("init", "-q")
        g("config", "user.email", "t@t.t")
        g("config", "user.name", "t")
        g("add", "-A")
        g("commit", "-qm", "baseline")
        (d / "src" / "users.py").write_text(edit(users), encoding="utf-8")
        g("add", "-A")
        g("commit", "-qm", "change")
        return analyze(str(d), base, "HEAD", load_settings())
    finally:
        shutil.rmtree(d, ignore_errors=True)


_RENAME = lambda s: s.replace("role", "user_role")  # noqa: E731
_DEFAULT = lambda s: s.replace('"viewer"', '"member"')  # noqa: E731
_REFACTOR = lambda s: s.replace(  # noqa: E731
    'return {"name": name, "role": role}', 'r = {"name": name, "role": role}\n    return r')
_DELETE_METHOD = lambda s: s.replace(_REMOVE_METHOD, "")  # noqa: E731
_ADD_PRIVATE = lambda s: s + '\n\ndef _internal_helper(x):\n    return x * 2\n'  # noqa: E731
_RENAME_AND_DELETE = lambda s: _DELETE_METHOD(_RENAME(s))  # noqa: E731


def _autofix_result():
    r = _analyze_after(_RENAME)
    return (r.sections_stale >= 1, r.autofixes_generated >= 1,
            any(x.action == Action.AUTO_FIX for x in r.results))


def _review_result():
    r = _analyze_after(_DELETE_METHOD)
    removed = [x for x in r.results if x.verdict.label == StalenessLabel.STALE]
    return (r.review_needed >= 1, all(x.action == Action.HUMAN_REVIEW for x in removed) if removed else False)


SCENARIOS = [
    # ---- predefined E2E (brief §24) ----
    Scenario("P6-01", 6, "High-confidence auto-fix scenario", "rename role->user_role",
             (True, True, True), _autofix_result),
    Scenario("P6-02", 6, "Medium-confidence human-review scenario", "delete remove_member",
             (True, True), _review_result),
    Scenario("P6-03", 6, "No-staleness scenario (internal refactor)", "rewrite body",
             0, lambda: _analyze_after(_REFACTOR).sections_stale),
    Scenario("P6-04", 6, "Unrelated code change scenario (new private helper)", "add _internal_helper",
             (0, 0), lambda: (lambda r: (r.sections_stale, r.autofixes_generated))(_analyze_after(_ADD_PRIVATE))),
    Scenario("P6-05", 6, "Multiple affected documentation sections", "rename + delete",
             True, lambda: _analyze_after(_RENAME_AND_DELETE).sections_stale >= 2),
    Scenario("P6-06", 6, "Failure/recovery: bad base ref does not crash", "base=NONEXISTENT",
             True, lambda: isinstance(_analyze_after(_RENAME, base="NONEXISTENTREF12345"), PipelineResult)),

    # ---- orchestrator-added ----
    Scenario("P6-07", 6, "[metrics] measured confusion over labelled fixtures", "compute_metrics",
             (3, 0, 0, 4), lambda: (lambda m: (m["tp"], m["fp"], m["fn"], m["tn"]))(compute_metrics()),
             kind="orchestrator"),
    Scenario("P6-08", 6, "[metrics] precision/recall/F1 == 1.0 on fixture set", "compute_metrics",
             (1.0, 1.0, 1.0),
             lambda: (lambda m: (m["precision"], m["recall"], m["f1"]))(compute_metrics()),
             kind="orchestrator"),
    Scenario("P6-09", 6, "[regression] analysis is deterministic across runs", "run twice",
             True, lambda: _analyze_after(_RENAME).sections_stale == _analyze_after(_RENAME).sections_stale,
             kind="orchestrator"),
    Scenario("P6-10", 6, "[edge] default-only change auto-fixes", "viewer->member",
             True, lambda: _analyze_after(_DEFAULT).autofixes_generated >= 1, kind="orchestrator"),
]
