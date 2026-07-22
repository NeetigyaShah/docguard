"""Phase 1 feature tests: repo walker, Python parser, Markdown parser, mapping."""

from pathlib import Path

from docguard.mapping.mapper import build_links, sections_for_unit
from docguard.models import CodeUnit, CodeUnitKind, MapMethod
from docguard.parsers.code_python import parse_python_file
from docguard.parsers.docs_markdown import parse_markdown_file
from docguard.parsers.repo_walker import find_code, find_docs
from docguard.providers.mock import MockEmbeddingProvider

ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "sample_project"


def _units():
    units = []
    for f in find_code(ROOT, ["src"]):
        units += parse_python_file(f, ROOT)
    return units


def _sections():
    secs = []
    for f in find_docs(ROOT, ["docs"]):
        secs += parse_markdown_file(f, ROOT)
    return secs


def _by_qual(units):
    return {u.qualified_name: u for u in units}


# --- repo walker ---
def test_walker_finds_code_and_docs():
    assert find_code(ROOT, ["src"]) == ["src/api.py", "src/cli.py", "src/config.py", "src/users.py"]
    assert find_docs(ROOT, ["docs"]) == ["docs/api.md", "docs/config.md"]


# --- python parser ---
def test_parser_extracts_all_unit_kinds():
    kinds = {u.kind for u in _units()}
    assert {
        CodeUnitKind.FUNCTION, CodeUnitKind.CLASS, CodeUnitKind.METHOD,
        CodeUnitKind.CONFIG_KEY, CodeUnitKind.CLI_COMMAND, CodeUnitKind.ENDPOINT,
    } <= kinds


def test_parser_signature_and_docstring():
    u = _by_qual(_units())["create_user"]
    assert u.signature == "(name: str, role: str='viewer')"
    assert "default role is viewer" in u.docstring.lower()
    assert set(u.symbols) >= {"create_user", "name", "role"}


def test_parser_methods_qualified():
    quals = _by_qual(_units())
    assert "UserService.remove_member" in quals
    assert quals["UserService.remove_member"].kind == CodeUnitKind.METHOD


def test_parser_config_cli_endpoint():
    quals = _by_qual(_units())
    assert quals["MAX_RETRIES"].kind == CodeUnitKind.CONFIG_KEY
    assert "cli:seed" in quals and quals["cli:seed"].kind == CodeUnitKind.CLI_COMMAND
    assert "GET /users" in quals and quals["GET /users"].kind == CodeUnitKind.ENDPOINT


def test_stable_ids():
    u = _by_qual(_units())["create_user"]
    assert u.id == CodeUnit.make_id("src/users.py", "create_user", CodeUnitKind.FUNCTION)
    # re-parse yields identical id
    assert u.id == _by_qual(_units())["create_user"].id


# --- markdown parser ---
def test_markdown_nested_heading_paths_and_refs():
    secs = {tuple(s.heading_path): s for s in _sections()}
    cu = secs[("API Reference", "Users", "create_user")]
    assert cu.level == 3
    assert set(cu.referenced_symbols) >= {"create_user", "role", "viewer"}
    assert cu.start_line > 0 and cu.end_line >= cu.start_line


# --- mapping ---
def test_mapping_links_expected_and_avoids_spurious():
    units, secs = _units(), _sections()
    links = build_links(units, secs, MockEmbeddingProvider(), threshold=0.35)
    quals = _by_qual(units)
    sec_id = {tuple(s.heading_path): s.id for s in secs}

    cu_id = quals["create_user"].id
    linked = set(sections_for_unit(cu_id, links))
    assert sec_id[("API Reference", "Users", "create_user")] in linked
    # not falsely linked to unrelated config sections
    assert sec_id[("Configuration", "Timeout")] not in linked
    assert sec_id[("Configuration", "Retries")] not in linked

    # config key maps to its section (exact)
    mr_id = quals["MAX_RETRIES"].id
    assert sec_id[("Configuration", "Retries")] in set(sections_for_unit(mr_id, links))


def test_mapping_exact_method_used_for_symbol_reference():
    units, secs = _units(), _sections()
    links = build_links(units, secs, MockEmbeddingProvider(), threshold=0.35)
    mr_id = _by_qual(units)["MAX_RETRIES"].id
    exact = [link for link in links if link.code_unit_id == mr_id and link.method == MapMethod.EXACT]
    assert exact
