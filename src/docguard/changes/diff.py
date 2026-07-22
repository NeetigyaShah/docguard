"""Git access for diffs — thin wrapper over the git CLI.

Provides changed files, changed line numbers, and file content at a revision.
`head=None` means the working tree.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _git(repo: str | Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.stdout


def changed_files(repo: str | Path, base: str, head: str | None = None) -> list[tuple[str, str]]:
    """Return (status, path) pairs. status in A/M/D/R... ; head=None → working tree."""
    args = ["diff", "--name-status", base] + ([head] if head else [])
    out = _git(repo, *args)
    pairs = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            pairs.append((parts[0][0], parts[-1]))
    return pairs


def file_at(repo: str | Path, ref: str | None, path: str) -> str:
    """File content at a revision. ref=None → working tree; missing → ''. """
    if ref is None:
        p = Path(repo) / path
        return p.read_text(encoding="utf-8") if p.exists() else ""
    return _git(repo, "show", f"{ref}:{path}")


def changed_line_numbers(repo: str | Path, base: str, head: str | None, path: str) -> set[int]:
    """New-file line numbers touched by the diff (for observability)."""
    args = ["diff", "--unified=0", base] + ([head] if head else []) + ["--", path]
    out = _git(repo, *args)
    lines: set[int] = set()
    new_ln = 0
    for line in out.splitlines():
        m = _HUNK.match(line)
        if m:
            new_ln = int(m.group(3))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.add(new_ln)
            new_ln += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass
        elif not line.startswith("\\"):
            new_ln += 1
    return lines
