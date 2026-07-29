"""GitHub integration: decide + apply.

The *decision* (what to do, what content) is pure and fully testable offline.
The *apply* step performs side effects via PyGithub and is import-guarded, so the
whole planning path — and its tests — run with no token and no network.

Policy: any high-confidence auto-fix → open a docs-fix branch/PR. Otherwise, if
anything is stale → comment on the PR. Never auto-merge. Loop prevention skips
DocGuard's own branches and `[docguard skip]`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from docguard.github.comment import build_comment
from docguard.models import Action, PipelineResult, StalenessLabel

BOT_BRANCH_PREFIX = "docguard/"
SKIP_TOKEN = "[docguard skip]"


def should_skip(*, head_ref: str = "", commit_message: str = "", actor: str = "") -> bool:
    """Loop prevention: never act on DocGuard's own PRs or skip-tagged runs."""
    if head_ref.startswith(BOT_BRANCH_PREFIX):
        return True
    if SKIP_TOKEN in (commit_message or ""):
        return True
    if actor.endswith("[bot]") and "docguard" in actor.lower():
        return True
    return False


@dataclass
class FileEdit:
    path: str
    new_content: str


@dataclass
class GithubPlan:
    mode: str                       # "pr" | "comment" | "none"
    comment_body: str = ""
    branch: str = ""
    pr_title: str = ""
    pr_body: str = ""
    file_edits: list[FileEdit] = field(default_factory=list)


def apply_repair_to_file(file_text: str, original_body: str, repaired_body: str) -> str:
    """Splice a repaired section body back into a doc file (content-based, span-local)."""
    return file_text.replace(original_body, repaired_body, 1)


def plan_actions(
    result: PipelineResult, *, run_id: str = "1", repo_root: str | Path | None = None
) -> GithubPlan:
    autofixes = [
        r for r in result.results
        if r.action == Action.AUTO_FIX and r.repair and r.repair.changed
    ]
    any_stale = any(r.verdict.label == StalenessLabel.STALE for r in result.results)
    comment = build_comment(result)

    if autofixes:
        # Build the FULL new text of each doc file by splicing every repaired body
        # into the file on disk. Anything we cannot read, or where the splice is a
        # no-op, is dropped — an edit must never carry empty/partial content, or the
        # auto-fix PR would truncate the documentation it was meant to repair.
        root = Path(repo_root or result.repo or ".")
        original: dict[str, str] = {}
        patched: dict[str, str] = {}
        for r in autofixes:
            path, rep = r.section.doc_path, r.repair
            if rep is None:  # unreachable: filtered above; keeps the type checker honest
                continue
            if path not in original:
                try:
                    original[path] = patched[path] = (root / path).read_text(encoding="utf-8")
                except OSError:
                    continue
            if path in patched:
                patched[path] = apply_repair_to_file(
                    patched[path], rep.original_content, rep.repaired_content
                )
        file_edits = [
            FileEdit(path=p, new_content=text)
            for p, text in patched.items()
            if text and text != original[p]
        ]
        if not file_edits:  # nothing safely applicable → fall back to a review comment
            return GithubPlan(mode="comment", comment_body=comment)
        return GithubPlan(
            mode="pr",
            branch=f"{BOT_BRANCH_PREFIX}fix-{run_id}",
            pr_title="docs: DocGuard auto-fix for stale documentation",
            pr_body=comment,
            comment_body=comment,
            file_edits=file_edits,
        )
    if any_stale:
        return GithubPlan(mode="comment", comment_body=comment)
    return GithubPlan(mode="none", comment_body=comment)


def run(
    result: PipelineResult,
    *,
    token: str = "",
    repo_slug: str = "",
    pr_number: int | None = None,
    head_ref: str = "",
    commit_message: str = "",
    run_id: str = "1",
    repo_root: str | Path | None = None,
    auto_fix: bool = True,
    client=None,
) -> dict:
    """Plan and (if a token/client is present) apply. Returns a status dict; never raises.

    `client` lets callers/tests inject a GitHub client (PyGithub-shaped); when
    absent and a token is set, a real PyGithub client is created.
    """
    if should_skip(head_ref=head_ref, commit_message=commit_message):
        return {"status": "skipped", "reason": "loop-prevention", "mode": "none"}

    plan = plan_actions(result, run_id=run_id, repo_root=repo_root)
    # `auto-fix: false` (the default) means: report, never open a PR.
    if plan.mode == "pr" and not auto_fix:
        plan = GithubPlan(mode="comment", comment_body=plan.comment_body)
    if client is None and (not token or not repo_slug):
        return {
            "status": "dry-run", "reason": "no GITHUB_TOKEN/repo (offline)",
            "mode": plan.mode, "branch": plan.branch, "comment_preview": plan.comment_body[:400],
        }
    try:
        if client is None:  # pragma: no cover - needs PyGithub + network
            from github import Github

            client = Github(token)
        return _apply(
            plan, client=client, repo_slug=repo_slug, pr_number=pr_number, head_ref=head_ref
        )
    except Exception as e:  # graceful API-error handling
        return {"status": "error", "mode": plan.mode, "error": str(e)[:300]}


def _apply(
    plan: GithubPlan, *, client, repo_slug: str, pr_number: int | None, head_ref: str = ""
) -> dict:
    repo = client.get_repo(repo_slug)
    if plan.mode == "comment" and pr_number:
        _upsert_comment(repo.get_pull(pr_number), plan.comment_body)
        return {"status": "commented", "mode": "comment", "pr": pr_number}
    if plan.mode == "pr":
        # Branch off (and target) the PR's own head branch when we know it: the repair
        # was computed against that checkout, so basing on the default branch could
        # splice into text that never existed there. Falls back to the default branch.
        base_branch = head_ref or repo.default_branch
        base_sha = repo.get_branch(base_branch).commit.sha
        repo.create_git_ref(ref=f"refs/heads/{plan.branch}", sha=base_sha)
        for edit in plan.file_edits:
            f = repo.get_contents(edit.path, ref=base_branch)
            repo.update_file(edit.path, "docs: DocGuard auto-fix", edit.new_content, f.sha, branch=plan.branch)
        pr = repo.create_pull(title=plan.pr_title, body=plan.pr_body, head=plan.branch, base=base_branch)
        return {"status": "pr-opened", "mode": "pr", "pr": pr.number, "branch": plan.branch}
    return {"status": "noop", "mode": plan.mode}


def _upsert_comment(pull, body: str) -> None:  # pragma: no cover
    from docguard.github.comment import _MARKER

    for c in pull.get_issue_comments():
        if _MARKER in (c.body or ""):
            c.edit(body)
            return
    pull.create_issue_comment(body)
