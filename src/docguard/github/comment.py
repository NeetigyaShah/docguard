"""Render a PR comment from a PipelineResult. Pure — no network, no secrets."""

from __future__ import annotations

from docguard.models import Action, PipelineResult, StalenessLabel

_MARKER = "<!-- docguard-report -->"  # used for loop prevention / idempotent updates


def build_comment(result: PipelineResult) -> str:
    lines = [
        _MARKER,
        "## 📘 DocGuard Results",
        "",
        f"- **Sections verified accurate:** {result.sections_verified_accurate}",
        f"- **Sections identified stale:** {result.sections_stale}",
        f"- **Auto-fixes generated:** {result.autofixes_generated}",
        f"- **Sections requiring human review:** {result.review_needed}",
    ]
    stale = [r for r in result.results if r.verdict.label == StalenessLabel.STALE]
    if stale:
        lines += ["", "### Affected sections", ""]
        for r in stale:
            tag = {
                Action.AUTO_FIX: "🟢 auto-fix",
                Action.HUMAN_REVIEW: "🟡 review",
                Action.REPORT: "🔴 report",
            }.get(r.action, "•")
            path = r.section.doc_path
            crumb = " / ".join(r.section.heading_path)
            lines.append(f"- `{path}` → **{crumb}** — {r.verdict.reason} _[{tag}]_")
    lines += ["", "<sub>DocGuard — self-healing docs. Add `[docguard skip]` to a commit to skip.</sub>"]
    return "\n".join(lines)
