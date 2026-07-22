"""One hand-verified REAL case on a fresh repo (httpx).

httpx.request(...) documents `follow_redirects` in docs/quickstart.md. Rename it
to `allow_redirects` (the historical `requests` name — a realistic breaking
change) and run verify + repair end-to-end on the real code + real doc.

Run: DOCGUARD_LLM_PROVIDER=openai (+ OPENAI_API_KEY / base url / model)
"""

from __future__ import annotations

import sys
from pathlib import Path

from docguard.changes.classify import classify_change
from docguard.config import load_settings
from docguard.parsers.code_python import parse_python_file, parse_python_source
from docguard.parsers.docs_markdown import parse_markdown_file
from docguard.providers.factory import get_llm_provider
from docguard.providers.mock import MockLLMProvider
from docguard.repair.repair import repair_section
from docguard.staleness.verifier import verify_section

REPO = Path("D:/_docguard_eval/httpx")
CODE = "httpx/_api.py"
DOC = "docs/quickstart.md"
OLD, NEW = "follow_redirects", "allow_redirects"


def main() -> int:
    units = parse_python_file(CODE, REPO)
    unit = next((u for u in units if u.qualified_name == "request"), None)
    if unit is None:
        print("request() not found")
        return 1

    impact = classify_change(unit, (parse_python_source(unit.source.replace(OLD, NEW), CODE) or [None])[0])

    secs = parse_markdown_file(DOC, REPO)
    section = max(secs, key=lambda s: s.content.count(OLD))
    print(f"real code:  {CODE}  request(... {OLD} ...) -> rename {OLD} -> {NEW}")
    print(f"real doc:   {DOC}  section: {' / '.join(section.heading_path)[:70]}")
    print(f"doc refs `{OLD}`: {section.content.count(OLD)}x\n")

    for label, llm in [("MOCK", MockLLMProvider()), ("REAL-LLM", get_llm_provider(load_settings()))]:
        if label == "REAL-LLM" and isinstance(llm, MockLLMProvider):
            print("REAL-LLM: provider is mock (set DOCGUARD_LLM_PROVIDER=openai) — skipped")
            continue
        v = verify_section(impact, unit, section, llm)
        print(f"[{label}] verdict={v.label.value} confidence={v.confidence} :: {v.reason[:110]}")
        if v.label.value == "stale":
            r = repair_section(v, impact, unit, section, llm)
            print(f"         repair changed={r.changed}")
            for ln in r.unified_diff.splitlines():
                if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")):
                    print(f"           {ln}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
