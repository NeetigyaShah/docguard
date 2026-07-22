"""One hand-verified REAL case: Pydantic `Field(frozen=...)` documented in
docs/concepts/fields.md. Rename the parameter and compare MOCK vs REAL LLM
end-to-end (verify + repair) on the real code + real doc text.

Run with the real provider via env:
  $env:DOCGUARD_LLM_PROVIDER='openai'  (+ OPENAI_API_KEY / base url / model)
"""

from __future__ import annotations

import sys
from pathlib import Path

from docguard.changes.classify import classify_change
from docguard.config import load_settings
from docguard.parsers.code_python import parse_python_file
from docguard.parsers.docs_markdown import parse_markdown_file
from docguard.providers.factory import get_llm_provider
from docguard.providers.mock import MockLLMProvider
from docguard.repair.repair import repair_section
from docguard.staleness.verifier import verify_section

REPO = Path("D:/_docguard_eval/pydantic")
CODE = "pydantic/fields.py"
DOC = "docs/concepts/fields.md"


def main():
    units = parse_python_file(CODE, REPO)
    field = next((u for u in units if u.qualified_name == "Field"), None)
    if field is None:
        print("Field() not found")
        return 1

    # deliberate breaking change: rename the documented `frozen` parameter
    from docguard.parsers.code_python import parse_python_source
    new_src = field.source.replace("frozen", "is_frozen")
    nu = parse_python_source(new_src, CODE)
    impact = classify_change(field, nu[0] if nu else None)

    secs = parse_markdown_file(DOC, REPO)
    # the real doc section that actually references `frozen`
    section = max(secs, key=lambda s: s.content.count("frozen"))
    print(f"real code:  {CODE}  Field(... frozen ...)  -> rename frozen -> is_frozen")
    print(f"real doc:   {DOC}  section: {' / '.join(section.heading_path)[:70]}")
    print(f"doc snippet: {section.content.strip().splitlines()[0][:100]}\n")

    for label, llm in [("MOCK", MockLLMProvider()), ("REAL-LLM", get_llm_provider(load_settings()))]:
        if label == "REAL-LLM" and isinstance(llm, MockLLMProvider):
            print("REAL-LLM: provider is mock (set DOCGUARD_LLM_PROVIDER=openai) — skipped")
            continue
        v = verify_section(impact, field, section, llm)
        print(f"[{label}] verdict={v.label.value} confidence={v.confidence} :: {v.reason[:110]}")
        if v.label.value == "stale":
            r = repair_section(v, impact, field, section, llm)
            print(f"         repair changed={r.changed}")
            if r.changed:
                for ln in r.unified_diff.splitlines():
                    if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")):
                        print(f"           {ln}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
