"""Phase 5 milestone scenarios: GitHub Action + PR/comment (mocked API).

Docker build (P5-01) is executed separately as evidence (too slow for the pytest
regression) and recorded to .orchestrator/tests.json.
"""

from __future__ import annotations

from pathlib import Path

from tests.milestones import Scenario

from docguard.github.comment import _MARKER, build_comment
from docguard.github.integration import plan_actions, run, should_skip
from docguard.models import (
    Action,
    ConfidenceLevel,
    DocSection,
    PipelineResult,
    Repair,
    RiskLevel,
    SectionResult,
    StalenessLabel,
    StalenessVerdict,
    ValidationResult,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _section(heading):
    return DocSection(id=f"docs/api.md#{heading}", doc_path="docs/api.md", heading=heading,
                      heading_path=["API", heading], content=f"`{heading}` accepts `role`.",
                      referenced_symbols=[heading])


def _result(*, with_autofix=True, with_review=True) -> PipelineResult:
    results = []
    autofix = review = stale = 0
    if with_autofix:
        s = _section("create_user")
        results.append(SectionResult(
            section=s, code_unit_id="cu",
            verdict=StalenessVerdict(doc_section_id=s.id, code_unit_id="cu",
                                     label=StalenessLabel.STALE, confidence=0.92,
                                     reason="param renamed", stale_claims=["role"], risk=RiskLevel.LOW),
            repair=Repair(doc_section_id=s.id, original_content="`create_user` accepts `role`.",
                          repaired_content="`create_user` accepts `user_role`.", changed=True),
            validation=ValidationResult(ok=True), confidence=ConfidenceLevel.HIGH, action=Action.AUTO_FIX,
        ))
        autofix += 1
        stale += 1
    if with_review:
        s = _section("delete_user")
        results.append(SectionResult(
            section=s, code_unit_id="du",
            verdict=StalenessVerdict(doc_section_id=s.id, code_unit_id="du",
                                     label=StalenessLabel.STALE, confidence=0.8,
                                     reason="feature removed", stale_claims=["delete_user"], risk=RiskLevel.HIGH),
            repair=Repair(doc_section_id=s.id, original_content="x", repaired_content="x", changed=False),
            validation=ValidationResult(ok=False), confidence=ConfidenceLevel.MEDIUM, action=Action.HUMAN_REVIEW,
        ))
        review += 1
        stale += 1
    return PipelineResult(sections_verified_accurate=2, sections_stale=stale,
                          autofixes_generated=autofix, review_needed=review, results=results)


# --- fake PyGithub-shaped client ---
class _Comment:
    def __init__(self, body):
        self.body = body
    def edit(self, body):
        self.body = body


class _Pull:
    def __init__(self, existing=None):
        self._comments = existing or []
        self.created = []
    def get_issue_comments(self):
        return self._comments
    def create_issue_comment(self, body):
        c = _Comment(body)
        self._comments.append(c)
        self.created.append(body)
        return c


class _Repo:
    default_branch = "main"
    def __init__(self, pull=None):
        self.calls = []
        self.pull = pull or _Pull()
    def get_pull(self, n):
        self.calls.append(("get_pull", n))
        return self.pull
    def get_branch(self, b):
        return type("B", (), {"commit": type("C", (), {"sha": "base"})()})()
    def create_git_ref(self, ref, sha):
        self.calls.append(("create_git_ref", ref))
    def get_contents(self, path, ref):
        return type("F", (), {"sha": "fsha"})()
    def update_file(self, path, msg, content, sha, branch):
        self.calls.append(("update_file", path))
    def create_pull(self, title, body, head, base):
        self.calls.append(("create_pull", head))
        return type("PR", (), {"number": 42})()


class _Client:
    def __init__(self, repo=None, raise_on=None):
        self._repo = repo or _Repo()
        self.raise_on = raise_on
    def get_repo(self, slug):
        if self.raise_on == "get_repo":
            raise RuntimeError("simulated GitHub API failure")
        return self._repo


def _mocked_comment():
    c = _Client()
    status = run(_result(with_autofix=False), client=c, token="x", repo_slug="o/r", pr_number=7)
    return status["status"], bool(c._repo.pull.created)


def _mocked_pr():
    c = _Client()
    status = run(_result(), client=c, token="x", repo_slug="o/r", pr_number=7)
    return status["status"], status.get("branch", "").startswith("docguard/fix-"), \
        ("create_pull", "docguard/fix-1") in [(k, v) for k, v in c._repo.calls if k == "create_pull"] or \
        any(k == "create_pull" for k, v in c._repo.calls)


def _upsert_edits_existing():
    existing = _Comment(f"{_MARKER}\nold body")
    c = _Client(repo=_Repo(pull=_Pull(existing=[existing])))
    run(_result(with_autofix=False), client=c, token="x", repo_slug="o/r", pr_number=7)
    return existing.body != f"{_MARKER}\nold body" and not c._repo.pull.created


SCENARIOS = [
    # ---- predefined (brief §23) ----
    Scenario("P5-02", 5, "Action metadata valid (docker + Dockerfile + inputs)", "action.yml",
             True, lambda: all(s in (REPO_ROOT / "action.yml").read_text() for s in
                               ['name: "DocGuard"', 'using: "docker"', 'image: "Dockerfile"',
                                "auto-fix:", "confidence-threshold:"])),
    Scenario("P5-03", 5, "Mocked GitHub API: comment posted", "run(mode=comment)",
             ("commented", True), _mocked_comment),
    Scenario("P5-04", 5, "PR comment generation (counts + refs)", "build_comment",
             True, lambda: all(s in build_comment(_result()) for s in
                               ["Sections verified accurate:", "Sections identified stale:",
                                "Auto-fixes generated:", "requiring human review:", "create_user"])),
    Scenario("P5-05", 5, "Fix branch/PR generation", "run(mode=pr)",
             ("pr-opened", True, True), _mocked_pr),
    Scenario("P5-06", 5, "Loop prevention (bot branch / skip token / normal)", "should_skip",
             (True, True, False),
             lambda: (should_skip(head_ref="docguard/fix-1"),
                      should_skip(commit_message="update [docguard skip]"),
                      should_skip(head_ref="feature/x", commit_message="normal"))),
    Scenario("P5-07", 5, "Missing credentials -> safe dry-run", "run(token='')",
             "dry-run", lambda: run(_result(), token="", repo_slug="")["status"]),
    Scenario("P5-08", 5, "API failure handled gracefully", "client raises",
             "error", lambda: run(_result(), client=_Client(raise_on="get_repo"),
                                  token="x", repo_slug="o/r")["status"]),

    # ---- orchestrator-added ----
    Scenario("P5-09", 5, "[security] comment contains no secret token", "no ghp_/token leak",
             True, lambda: "ghp_" not in build_comment(_result()) and "token" not in build_comment(_result()).lower(),
             kind="orchestrator"),
    Scenario("P5-10", 5, "[edge] no staleness -> plan mode none", "empty result",
             "none", lambda: plan_actions(PipelineResult()).mode, kind="orchestrator"),
    Scenario("P5-11", 5, "[regression] PR body carries report marker (idempotency)", "plan pr_body",
             True, lambda: _MARKER in plan_actions(_result()).pr_body, kind="orchestrator"),
    Scenario("P5-12", 5, "[edge] comment upsert edits existing, no duplicate", "existing marker comment",
             True, _upsert_edits_existing, kind="orchestrator"),
]
