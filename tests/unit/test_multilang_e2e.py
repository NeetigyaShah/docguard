"""End-to-end polyglot proof: the SAME analyze() pipeline heals docs for a
non-Python repo. Guards the integration seam (universal parser -> detect -> map
-> verify -> repair) that the per-language unit tests don't cover on their own.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from docguard.config import load_settings
from docguard.pipeline import analyze


def _git(d: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)


def _repo(src_rel: str, src_before: str, src_after: str, doc: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="dg_e2e_"))
    (d / "src").mkdir()
    (d / "docs").mkdir()
    (d / src_rel).parent.mkdir(parents=True, exist_ok=True)
    (d / src_rel).write_text(src_before, encoding="utf-8")
    (d / "docs" / "api.md").write_text(doc, encoding="utf-8")
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "e@e.e")
    _git(d, "config", "user.name", "e")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "base")
    (d / src_rel).write_text(src_after, encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "change")
    return d


def test_typescript_repo_heals_end_to_end():
    d = _repo(
        "src/api.ts",
        'export function createUser(name: string, role = "viewer") {\n  return {name, role};\n}\n',
        'export function createUser(name: string, userRole = "viewer") {\n  return {name, userRole};\n}\n',
        "# API\n\n## createUser\n\n`createUser` accepts `name` and `role`. The default `role` is `viewer`.\n",
    )
    res = analyze(str(d), "HEAD~1", "HEAD", load_settings())
    assert res.sections_stale == 1
    repaired = [r for r in res.results if getattr(r, "repair", None) and r.repair.changed]
    assert repaired, "expected an auto-generated doc fix for the TS rename"
    assert "userRole" in repaired[0].repair.repaired_content
    assert "`role`" not in repaired[0].repair.repaired_content


def test_java_repo_detects_stale_end_to_end():
    d = _repo(
        "src/UserService.java",
        "public class UserService {\n  public void addMember(String name, String role) { }\n}\n",
        "public class UserService {\n  public void addMember(String name, String userRole) { }\n}\n",
        "# API\n\n## addMember\n\n`addMember` takes a `name` and a `role`.\n",
    )
    res = analyze(str(d), "HEAD~1", "HEAD", load_settings())
    assert res.sections_stale >= 1  # Java param rename flagged the stale doc
