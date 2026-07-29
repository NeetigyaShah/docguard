"""DocGuard CLI: `analyze`, `action`, `demo`."""

from __future__ import annotations

import argparse
import json
import os
import sys

from docguard.config import load_settings
from docguard.github.integration import run as github_run
from docguard.pipeline import analyze


def _result_json(result) -> str:
    return result.model_dump_json(indent=2)


def cmd_analyze(args) -> int:
    settings = load_settings()
    result = analyze(args.repo, args.base, args.head, settings)
    print(_result_json(result))
    return 0


def cmd_action(args) -> int:
    """GitHub Action entrypoint — reads config from env, comments or opens a PR."""
    settings = load_settings()
    base = args.base or os.environ.get("DOCGUARD_BASE", "HEAD~1")
    head = args.head or os.environ.get("DOCGUARD_HEAD") or None
    repo = args.repo or os.environ.get("GITHUB_WORKSPACE", ".")
    result = analyze(repo, base, head, settings)

    pr_number = None
    event = os.environ.get("GITHUB_EVENT_PATH")
    if event and os.path.exists(event):
        try:
            with open(event, encoding="utf-8") as f:
                pr_number = json.load(f).get("pull_request", {}).get("number")
        except Exception:
            pr_number = None

    status = github_run(
        result,
        token=settings.github_token,
        repo_slug=os.environ.get("GITHUB_REPOSITORY", ""),
        pr_number=pr_number,
        head_ref=os.environ.get("GITHUB_HEAD_REF", ""),
        commit_message=os.environ.get("DOCGUARD_COMMIT_MSG", ""),
        run_id=os.environ.get("GITHUB_RUN_ID", "1"),
        repo_root=repo,
        auto_fix=settings.auto_fix,
    )
    print(json.dumps({"summary": {
        "accurate": result.sections_verified_accurate,
        "stale": result.sections_stale,
        "autofixes": result.autofixes_generated,
        "review": result.review_needed,
    }, "github": status}, indent=2))
    # never fail the CI job just because docs are stale
    return 0


def cmd_demo(args) -> int:
    from docguard.demo import run_demo

    run_demo()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docguard", description="Self-healing technical docs")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Analyze a diff and print stale-doc report as JSON")
    a.add_argument("--repo", default=".")
    a.add_argument("--base", default="HEAD~1")
    a.add_argument("--head", default=None)
    a.set_defaults(func=cmd_analyze)

    g = sub.add_parser("action", help="GitHub Action entrypoint (comment or PR)")
    g.add_argument("--repo", default=None)
    g.add_argument("--base", default=None)
    g.add_argument("--head", default=None)
    g.set_defaults(func=cmd_action)

    d = sub.add_parser("demo", help="Run the deterministic offline end-to-end demo")
    d.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
