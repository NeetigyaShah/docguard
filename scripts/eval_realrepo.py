"""Evaluate DocGuard against a REAL repository.

Auto-discovers documented public callables (a symbol referenced by name in a
mapped doc section), then for each target builds a scoped temp git repo
containing that real source file + the real doc that references it, applies a
deliberate breaking mutation (rename a parameter / change a default), runs the
full pipeline, and records whether the stale doc was correctly flagged. Also
runs negative controls (whitespace/comment-only edits that must NOT be flagged).

Honest measurement: reports TP / FP / FN and sample repairs from executed runs.

Usage:
  python scripts/eval_realrepo.py --repo D:/_docguard_eval/pydantic \
      --src pydantic --docs docs --targets 15
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from docguard.config import load_settings
from docguard.mapping.mapper import build_links, sections_for_unit
from docguard.models import CodeUnitKind
from docguard.parsers.code_python import parse_python_file
from docguard.parsers.docs_markdown import parse_markdown_file
from docguard.parsers.repo_walker import find_code, find_docs
from docguard.pipeline import analyze
from docguard.providers.mock import MockEmbeddingProvider


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)


def _first_param(signature: str) -> str | None:
    inside = signature.strip().lstrip("(").rstrip(")")
    for part in inside.split(","):
        name = part.split(":")[0].split("=")[0].strip().lstrip("*")
        if name and name not in ("self", "cls", "/"):
            return name
    return None


def _default_pair(source: str) -> tuple[str, str] | None:
    # find a simple `name: type = LITERAL` default we can flip
    m = re.search(r"(\w+)\s*(?::[^=,)]+)?=\s*(True|False|None|\d+)", source)
    if m:
        flip = {"True": "False", "False": "True", "None": "0"}.get(m.group(2), "999")
        return m.group(2), flip
    return None


def discover_targets(repo: Path, src: list[str], docs: list[str], settings):
    units = [u for f in find_code(repo, src) for u in _safe_parse(f, repo)]
    secs = [s for f in find_docs(repo, docs) for s in _safe_md(f, repo)]
    # scope mapping cost: only units that are public callables with a param
    callables = [
        u for u in units
        if u.kind in (CodeUnitKind.FUNCTION, CodeUnitKind.METHOD)
        and not u.name.startswith("_")
        and _first_param(u.signature)
    ]
    links = build_links(callables, secs, MockEmbeddingProvider(), settings.similarity_threshold)
    secs_by_id = {s.id: s for s in secs}
    targets = []
    for u in callables:
        linked = [secs_by_id[i] for i in sections_for_unit(u.id, links) if i in secs_by_id]
        # keep only targets whose FIRST param name actually appears in a linked doc
        p = _first_param(u.signature)
        doc = next((s for s in linked if p and re.search(rf"\b{re.escape(p)}\b", s.content)), None)
        if doc:
            targets.append((u, doc, p))
    return targets


def _safe_parse(f, repo):
    try:
        return parse_python_file(f, repo)
    except Exception:
        return []


def _safe_md(f, repo):
    try:
        return parse_markdown_file(f, repo)
    except Exception:
        return []


def _scoped_repo(repo: Path, src_file: str, doc_file: str, mutate) -> Path:
    d = Path(tempfile.mkdtemp(prefix="dg_real_"))
    (d / "src").mkdir()
    (d / "docs").mkdir()
    src_text = (repo / src_file).read_text(encoding="utf-8", errors="replace")
    doc_text = (repo / doc_file).read_text(encoding="utf-8", errors="replace")
    (d / "src" / "mod.py").write_text(src_text, encoding="utf-8")
    (d / "docs" / "doc.md").write_text(doc_text, encoding="utf-8")
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "e@e.e")
    _git(d, "config", "user.name", "e")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "base")
    mutated = mutate(src_text)
    (d / "src" / "mod.py").write_text(mutated, encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "change")
    return d


def evaluate(repo: Path, src, docs, n_targets: int) -> dict:
    settings = load_settings()
    targets = discover_targets(repo, src, docs, settings)
    print(f"discovered {len(targets)} documented mutable targets; testing up to {n_targets}\n")
    tp = fp = fn = 0
    samples, negatives_fp = [], 0
    used = targets[:n_targets]

    for u, doc, param in used:
        # POSITIVE: rename the documented first parameter -> docs become stale
        def mutate(text, param=param):
            return re.sub(rf"\b{re.escape(param)}\b", f"{param}_renamed", text, count=8)

        d = _scoped_repo(repo, u.file, doc.doc_path, mutate)
        try:
            res = analyze(str(d), "HEAD~1", "HEAD", settings)
            flagged = res.sections_stale >= 1
            repair = next((r.repair.repaired_content for r in res.results
                           if r.repair and r.repair.changed), None)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        if flagged:
            tp += 1
        else:
            fn += 1
        samples.append({
            "symbol": u.qualified_name, "param": param, "doc": doc.doc_path,
            "flagged_stale": flagged, "repair_generated": bool(repair),
            "repair_preview": (repair.splitlines()[0][:120] if repair else None),
        })
        print(f"  [{'TP' if flagged else 'FN'}] {u.qualified_name}(rename {param}) "
              f"doc={Path(doc.doc_path).name} fix={'yes' if repair else 'no'}")

    # NEGATIVE CONTROLS: comment-only change must NOT be flagged
    for u, doc, _param in used[: min(5, len(used))]:
        def mutate_neg(text):
            return text.replace("\n\n", "\n\n# harmless comment\n", 1)

        d = _scoped_repo(repo, u.file, doc.doc_path, mutate_neg)
        try:
            res = analyze(str(d), "HEAD~1", "HEAD", settings)
            if res.sections_stale >= 1:
                fp += 1
                negatives_fp += 1
        finally:
            shutil.rmtree(d, ignore_errors=True)

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "repo": str(repo), "targets_tested": len(used),
        "tp": tp, "fp": fp, "fn": fn, "negative_controls": min(5, len(used)),
        "false_positives_on_negatives": negatives_fp,
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "samples": samples,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--src", default="src")
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--targets", type=int, default=15)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    result = evaluate(Path(args.repo), args.src.split(","), args.docs.split(","), args.targets)
    print("\n=== REAL-REPO RESULT ===")
    print(f"tp={result['tp']} fp={result['fp']} fn={result['fn']}  "
          f"precision={result['precision']} recall={result['recall']} f1={result['f1']}")
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
