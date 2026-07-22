"""Deterministic, fully-offline end-to-end demo + measured metrics.

Self-contained: builds a throwaway git repo from embedded sources, applies the
canonical public-API change (rename `role`->`user_role`, default
`viewer`->`member`), runs the full pipeline, and prints each stage. Then runs
negative scenarios and computes precision/recall/F1 from executed fixtures
(never fabricated). Requires no API keys.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from docguard.changes.classify import classify_change
from docguard.config import load_settings
from docguard.github.integration import run as github_run
from docguard.models import StalenessLabel
from docguard.parsers.code_python import parse_python_source
from docguard.parsers.docs_markdown import parse_markdown_source
from docguard.pipeline import analyze
from docguard.providers.mock import MockLLMProvider
from docguard.staleness.verifier import verify_section

USERS_PY = '''\
DEFAULT_ROLE = "viewer"


def create_user(name: str, role: str = "viewer") -> dict:
    """Create a user with a name and role."""
    return {"name": name, "role": role}


class UserService:
    """Manages users."""

    def remove_member(self, name: str) -> None:
        """Remove a member by name."""
        self._members = [m for m in getattr(self, "_members", []) if m["name"] != name]
'''

API_MD = '''\
# API Reference

## Users

### create_user

`create_user` accepts `name` and `role`. The default `role` is `viewer`.
It returns a dictionary containing the user's name and role.

### UserService.remove_member

`remove_member` removes a member by name from the service.
'''

# canonical public-API change: rename role->user_role AND default viewer->member
CHANGED_USERS_PY = (
    USERS_PY.replace('role: str = "viewer"', 'user_role: str = "member"')
    .replace('"role": role', '"role": user_role')
)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def build_demo_repo() -> Path:
    d = Path(tempfile.mkdtemp(prefix="docguard_demo_"))
    (d / "src").mkdir()
    (d / "docs").mkdir()
    (d / "src" / "users.py").write_text(USERS_PY, encoding="utf-8")
    (d / "docs" / "api.md").write_text(API_MD, encoding="utf-8")
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "demo@docguard.local")
    _git(d, "config", "user.name", "DocGuard Demo")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "baseline: accurate code + docs")
    (d / "src" / "users.py").write_text(CHANGED_USERS_PY, encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "feat: rename role->user_role, default viewer->member")
    return d


# --------------------------------------------------------------------------- #
# metrics — computed from executed fixtures, not fabricated
# --------------------------------------------------------------------------- #
def compute_metrics() -> dict:
    units = {u.qualified_name: u for u in parse_python_source(USERS_PY, "src/users.py")}
    secs = {tuple(s.heading_path): s for s in parse_markdown_source(API_MD, "docs/api.md")}
    cu = units["create_user"]
    cu_sec = secs[("API Reference", "Users", "create_user")]
    rm = units["UserService.remove_member"]
    rm_sec = secs[("API Reference", "Users", "UserService.remove_member")]
    llm = MockLLMProvider()

    def edit(unit, fn):
        return classify_change(unit, parse_python_source(fn(unit.source), unit.file)[0])

    # (name, impact, code_unit, section, truth_is_stale)
    cases = [
        ("rename param", edit(cu, lambda s: s.replace("role", "user_role")), cu, cu_sec, True),
        ("changed default", edit(cu, lambda s: s.replace('"viewer"', '"member"')), cu, cu_sec, True),
        ("removed feature", classify_change(rm, None), rm, rm_sec, True),
        ("internal refactor", edit(cu, lambda s: s.replace(
            'return {"name": name, "role": role}', 'r = {"name": name, "role": role}\n    return r')),
            cu, cu_sec, False),
        ("whitespace only", edit(cu, lambda s: s.replace("return {", "\n    return {")), cu, cu_sec, False),
        ("comment only", edit(cu, lambda s: s.replace(
            "return {", "# note\n    return {")), cu, cu_sec, False),
        ("unrelated config", classify_change(None, units["DEFAULT_ROLE"]), units["DEFAULT_ROLE"], cu_sec, False),
    ]
    tp = fp = fn = tn = 0
    rows = []
    for name, impact, unit, section, truth in cases:
        pred = verify_section(impact, unit, section, llm).label == StalenessLabel.STALE
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and truth:
            fn += 1
        else:
            tn += 1
        rows.append((name, truth, pred))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "rows": rows,
    }


def run_demo() -> dict:
    print("=" * 70)
    print("DocGuard — deterministic offline end-to-end demo")
    print("=" * 70)
    repo = build_demo_repo()
    try:
        print("\n[1] Developer changed the public API of create_user:")
        print("    - parameter  role  ->  user_role")
        print("    - default    'viewer'  ->  'member'")
        settings = load_settings()
        result = analyze(str(repo), "HEAD~1", "HEAD", settings)

        print("\n[2-6] Diff -> semantic units -> meaningful change -> mapping -> candidates")
        print(f"      LLM calls: {result.llm_calls} (only meaningful, mapped candidates)")
        print("\n[7] Staleness verification + [8-9] repair & validation + [10] confidence:")
        for r in result.results:
            crumb = " / ".join(r.section.heading_path)
            print(f"    • {r.section.doc_path} :: {crumb}")
            print(f"      verdict={r.verdict.label.value} conf={r.verdict.confidence} "
                  f"action={r.action.value if r.action else '-'}")
            print(f"      reason: {r.verdict.reason}")
            if r.repair and r.repair.changed:
                print("      --- repaired section (targeted) ---")
                for line in r.repair.repaired_content.splitlines():
                    print(f"        {line}")

        print("\n[11] GitHub integration payload (offline dry-run):")
        gh = github_run(result, token="", repo_slug="")
        print(f"      mode={gh['mode']} status={gh['status']}")

        print("\n[12] Summary:")
        print(f"      accurate={result.sections_verified_accurate} stale={result.sections_stale} "
              f"auto-fixes={result.autofixes_generated} review={result.review_needed}")

        m = compute_metrics()
        print("\n" + "=" * 70)
        print("MEASURED METRICS (from executed fixtures — 7 labelled scenarios)")
        print("=" * 70)
        for name, truth, pred in m["rows"]:
            ok = "OK " if truth == pred else "XX "
            print(f"  {ok} {name:20} truth_stale={truth!s:5} predicted_stale={pred}")
        print(f"\n  TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}")
        print(f"  precision={m['precision']}  recall={m['recall']}  F1={m['f1']}")
        print("=" * 70)
        return {"result": result, "metrics": m}
    finally:
        shutil.rmtree(repo, ignore_errors=True)
