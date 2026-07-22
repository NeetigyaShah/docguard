"""Phase 2 milestone scenarios (predefined A-G + orchestrator-added)."""

from __future__ import annotations

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from tests.milestones import Scenario

from docguard.changes.classify import classify_change, detect_changes
from docguard.models import ChangeImpact, ChangeKind
from docguard.parsers.code_python import parse_python_source

_ORDER = [
    ChangeKind.WHITESPACE, ChangeKind.COMMENT, ChangeKind.FORMATTING, ChangeKind.TEST_ONLY,
    ChangeKind.INTERNAL_REFACTOR, ChangeKind.PARAM_RENAMED, ChangeKind.PARAM_REMOVED,
    ChangeKind.PARAM_ADDED, ChangeKind.DEFAULT_CHANGED, ChangeKind.CONFIG_CHANGE,
    ChangeKind.CLI_CHANGE, ChangeKind.ENDPOINT_CHANGE, ChangeKind.REMOVED_PUBLIC,
    ChangeKind.CAPABILITY_ADDED, ChangeKind.CAPABILITY_REMOVED,
]


def _primary(imp: ChangeImpact) -> str:
    idx = {k: i for i, k in enumerate(_ORDER)}
    ranked = sorted(imp.change_kinds, key=lambda k: idx.get(k, 99))
    return ranked[0].value if ranked else "none"


def _u(src, path="src/users.py"):
    us = parse_python_source(src, path)
    return us[0] if us else None


def _headline(old_src, new_src, path="src/users.py", is_test=False):
    imp = classify_change(_u(old_src, path) if old_src else None,
                          _u(new_src, path) if new_src else None, is_test=is_test)
    if imp is None:
        return ("none", None)
    return (_primary(imp), imp.meaningful)


def _endpoint_flags(old_src, new_src):
    imp = classify_change(_u(old_src, "src/api.py"), _u(new_src, "src/api.py"))
    return (ChangeKind.ENDPOINT_CHANGE in imp.change_kinds, imp.meaningful)


BASE = 'def create_user(name, role="viewer"):\n    return {"name": name}\n'


@lru_cache(maxsize=1)
def _git_rename_impacts() -> tuple:
    """Real git repo: commit baseline, rename a param, detect changes across HEAD~1..HEAD."""
    d = Path(tempfile.mkdtemp(prefix="docguard_p2_"))
    (d / "src").mkdir()

    def g(*a):
        subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)

    g("init", "-q")
    g("config", "user.email", "t@t.t")
    g("config", "user.name", "t")
    (d / "src" / "users.py").write_text(BASE, encoding="utf-8")
    g("add", "-A")
    g("commit", "-qm", "base")
    (d / "src" / "users.py").write_text(BASE.replace("role", "user_role"), encoding="utf-8")
    g("add", "-A")
    g("commit", "-qm", "rename")
    impacts = detect_changes(str(d), "HEAD~1", "HEAD", ["src"])
    return tuple((i.unit_name, i.meaningful, tuple(k.value for k in i.change_kinds)) for i in impacts)


_ADD_PARAM = 'def create_user(name, role="viewer", active=True):\n    return {"name": name}\n'
_RM_PARAM = 'def create_user(name):\n    return {"name": name}\n'
_ENDPOINT_OLD = '@app.get("/users")\ndef list_users(limit=10):\n    return []\n'
_ENDPOINT_NEW = '@app.get("/users")\ndef list_users(limit=25):\n    return []\n'
_CFG_OLD = "MAX_RETRIES = 3\n"
_CFG_NEW = "MAX_RETRIES = 5\n"

SCENARIOS = [
    # ---- predefined A-G (brief §20) ----
    Scenario("P2-A", 2, "Whitespace-only change is down-ranked", "add blank line",
             ("whitespace", False), lambda: _headline(BASE, 'def create_user(name, role="viewer"):\n\n    return {"name": name}\n')),
    Scenario("P2-B", 2, "Comment-only change is down-ranked", "add a comment",
             ("comment", False), lambda: _headline(BASE, 'def create_user(name, role="viewer"):\n    # hi\n    return {"name": name}\n')),
    Scenario("P2-C", 2, "Renamed parameter is meaningful", "role -> user_role",
             ("param_renamed", True), lambda: _headline(BASE, BASE.replace("role", "user_role"))),
    Scenario("P2-D", 2, "Changed default is meaningful", 'viewer -> member',
             ("default_changed", True), lambda: _headline(BASE, BASE.replace("viewer", "member"))),
    Scenario("P2-E", 2, "New config key is meaningful", "add MAX_RETRIES",
             ("config_change", True), lambda: _headline(None, _CFG_OLD, "src/config.py")),
    Scenario("P2-F", 2, "Removed public function is meaningful", "delete create_user",
             ("removed_public", True), lambda: _headline(BASE, None)),
    Scenario("P2-G", 2, "Internal refactor (same signature) is down-ranked", "rewrite body",
             ("internal_refactor", False), lambda: _headline(BASE, 'def create_user(name, role="viewer"):\n    r = {"name": name}\n    return r\n')),

    # ---- orchestrator-added ----
    Scenario("P2-08", 2, "[edge] identical source yields no change", "no-op edit",
             ("none", None), lambda: _headline(BASE, BASE), kind="orchestrator"),
    Scenario("P2-09", 2, "[negative] test-file change is TEST_ONLY, not meaningful", "edit under tests/",
             ("test_only", False), lambda: _headline(BASE, BASE.replace("viewer", "member"), "tests/test_x.py", True),
             kind="orchestrator"),
    Scenario("P2-10", 2, "[edge] added parameter is meaningful", "add active=True",
             ("param_added", True), lambda: _headline(BASE, _ADD_PARAM), kind="orchestrator"),
    Scenario("P2-11", 2, "[edge] removed parameter is meaningful", "drop role",
             ("param_removed", True), lambda: _headline(BASE, _RM_PARAM), kind="orchestrator"),
    Scenario("P2-12", 2, "[integration] detect_changes over real git repo (rename)", "git HEAD~1..HEAD",
             (("create_user", True, ("param_renamed", "signature_change", "public_api_change")),),
             _git_rename_impacts, kind="orchestrator"),
    Scenario("P2-13", 2, "[edge] endpoint change is tagged endpoint_change + meaningful", "limit 10->25",
             (True, True), lambda: _endpoint_flags(_ENDPOINT_OLD, _ENDPOINT_NEW),
             kind="orchestrator"),
    Scenario("P2-14", 2, "[regression] config value change is CONFIG_CHANGE", "MAX_RETRIES 3->5",
             ("config_change", True), lambda: _headline(_CFG_OLD, _CFG_NEW, "src/config.py"),
             kind="orchestrator"),
]
