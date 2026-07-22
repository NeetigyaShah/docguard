"""Phase 0 backbone: models, config, deterministic mock providers."""

from docguard.config import load_settings
from docguard.models import (
    ChangeImpact,
    ChangeKind,
    CodeUnit,
    CodeUnitKind,
    DocSection,
    StalenessLabel,
)
from docguard.providers.factory import get_embedding_provider, get_llm_provider
from docguard.providers.mock import MockEmbeddingProvider, MockLLMProvider, parse_params


def _unit(src_old="def create_user(name, role='viewer'): ...",
          src_new="def create_user(name, user_role='viewer'): ..."):
    cu = CodeUnit(
        id=CodeUnit.make_id("src/users.py", "create_user", CodeUnitKind.FUNCTION),
        kind=CodeUnitKind.FUNCTION, name="create_user", qualified_name="create_user",
        signature="(name, role='viewer')", file="src/users.py", start_line=1, end_line=1,
        symbols=["create_user", "role"],
    )
    return cu, src_old, src_new


def test_code_unit_id_stable():
    a = CodeUnit.make_id("src/u.py", "create_user", CodeUnitKind.FUNCTION)
    b = CodeUnit.make_id("src/u.py", "create_user", CodeUnitKind.FUNCTION)
    assert a == b == "src/u.py::create_user::function"


def test_doc_section_id_uses_heading_path():
    sid = DocSection.make_id("docs/api.md", ["API", "Users", "create_user"])
    assert sid == "docs/api.md#API/Users/create_user"


def test_config_offline_defaults():
    s = load_settings()
    assert s.llm_provider == "mock"
    assert s.embedding_provider == "mock"
    assert 0 < s.similarity_threshold < 1
    assert s.high_confidence > s.medium_confidence


def test_factory_returns_mocks_by_default():
    s = load_settings()
    assert isinstance(get_llm_provider(s), MockLLMProvider)
    assert isinstance(get_embedding_provider(s), MockEmbeddingProvider)


def test_mock_embeddings_deterministic_and_normalized():
    e = MockEmbeddingProvider()
    v1 = e.embed(["create user role viewer"])[0]
    v2 = e.embed(["create user role viewer"])[0]
    assert v1 == v2  # deterministic
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-9  # unit norm
    other = e.embed(["completely unrelated content"])[0]
    assert sum(a * b for a, b in zip(v1, other)) < sum(a * b for a, b in zip(v1, v1))


def test_parse_params_handles_defaults():
    p = parse_params("def create_user(name: str, role: str = 'viewer'): ...")
    assert p == [("name", None), ("role", "'viewer'")]


def test_mock_llm_detects_renamed_param():
    cu, old, new = _unit()
    section = DocSection(
        id="docs/api.md#create_user", doc_path="docs/api.md", heading="create_user",
        heading_path=["create_user"], content="create_user accepts name and role. Default role is viewer.",
        referenced_symbols=["create_user"],
    )
    impact = ChangeImpact(
        file="src/users.py", code_unit_id=cu.id, unit_name="create_user",
        kind=CodeUnitKind.FUNCTION, old_source=old, new_source=new,
        change_kinds=[ChangeKind.PARAM_RENAMED], meaningful=True,
    )
    llm = MockLLMProvider()
    verdict = llm.verify_staleness(impact=impact, code_unit=cu, section=section)
    assert verdict.label == StalenessLabel.STALE
    assert "role" in verdict.stale_claims
    assert llm.calls == 1


def test_mock_llm_accurate_on_internal_refactor():
    cu, old, _new = _unit()
    section = DocSection(
        id="docs/api.md#create_user", doc_path="docs/api.md", heading="create_user",
        heading_path=["create_user"], content="create_user accepts name and role.",
        referenced_symbols=["create_user"],
    )
    impact = ChangeImpact(
        file="src/users.py", code_unit_id=cu.id, unit_name="create_user",
        old_source=old, new_source=old, change_kinds=[ChangeKind.INTERNAL_REFACTOR],
        meaningful=False,
    )
    verdict = MockLLMProvider().verify_staleness(impact=impact, code_unit=cu, section=section)
    assert verdict.label == StalenessLabel.ACCURATE
