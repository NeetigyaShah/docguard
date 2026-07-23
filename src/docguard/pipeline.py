"""End-to-end pipeline: git diff → stale doc sections → gated corrections.

Wires every stage into a single `analyze()` that returns a PipelineResult (the
audit-trail + GitHub payload). Cost control: candidate filtering via mapping
happens before any LLM call, and only meaningful changes are verified.
"""

from __future__ import annotations

from pathlib import Path

from docguard.changes.classify import detect_changes
from docguard.changes.diff import file_at
from docguard.confidence.policy import decide
from docguard.config import Settings, load_settings
from docguard.mapping.mapper import build_links
from docguard.models import Action, PipelineResult, StalenessLabel
from docguard.parsers.code import parse_code_file, parse_code_source
from docguard.parsers.docs_markdown import parse_markdown_file
from docguard.parsers.repo_walker import find_code, find_docs
from docguard.providers.factory import get_embedding_provider, get_llm_provider
from docguard.repair.repair import repair_section
from docguard.repair.validate import validate_repair
from docguard.staleness.verifier import verify_changes


def analyze(
    repo: str, base: str, head: str | None = None, settings: Settings | None = None
) -> PipelineResult:
    settings = settings or load_settings()
    repo_path = Path(repo)

    # Neetigya, 2026-07-23: parse via the universal router (parse_code_file /
    # parse_code_source) so the whole pipeline heals docs for py/ts/js/java, not just Python.
    head_units = [u for f in find_code(repo, settings.src_path_list()) for u in parse_code_file(f, repo)]
    sections = [s for f in find_docs(repo, settings.docs_path_list()) for s in parse_markdown_file(f, repo)]

    impacts = detect_changes(repo, base, head, settings.src_path_list())
    by_id = {u.id: u for u in head_units}
    impact_by_unit = {}
    extra = []
    for imp in impacts:
        if imp.code_unit_id:
            impact_by_unit[imp.code_unit_id] = imp
            if imp.code_unit_id not in by_id:  # removed unit → reconstruct from base
                for u in parse_code_source(file_at(repo, base, imp.file), imp.file):
                    if u.id == imp.code_unit_id:
                        by_id[u.id] = u
                        extra.append(u)

    embedder = get_embedding_provider(settings)
    cache = str(repo_path / ".docguard_index" / "embeddings.json")
    links = build_links(head_units + extra, sections, embedder, settings.similarity_threshold, cache)

    llm = get_llm_provider(settings)
    secs_by_id = {s.id: s for s in sections}
    verified = verify_changes(impacts, by_id, secs_by_id, links, llm)

    results, accurate, stale, autofix, review = [], 0, 0, 0, 0
    for r in verified:
        if r.verdict.label == StalenessLabel.ACCURATE:
            accurate += 1
            results.append(r)
            continue
        if r.verdict.label == StalenessLabel.UNRELATED:
            continue
        # STALE → repair + validate + gate
        stale += 1
        impact = impact_by_unit[r.code_unit_id]
        unit = by_id[r.code_unit_id]
        repair = repair_section(r.verdict, impact, unit, r.section, llm)
        validation = validate_repair(repair, r.verdict)
        level, action = decide(r.verdict, repair, validation, settings)
        if action == Action.AUTO_FIX:
            autofix += 1
        else:
            review += 1
        results.append(r.model_copy(update={
            "repair": repair, "validation": validation, "confidence": level, "action": action,
        }))

    return PipelineResult(
        repo=repo, base=base, head=head or "WORKTREE",
        sections_verified_accurate=accurate, sections_stale=stale,
        autofixes_generated=autofix, review_needed=review,
        results=results, llm_calls=getattr(llm, "calls", 0),
    )
