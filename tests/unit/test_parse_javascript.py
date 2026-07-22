"""JavaScript extractor: extraction correctness + change detection."""

from __future__ import annotations

from docguard.changes.classify import classify_change
from docguard.models import ChangeKind, CodeUnitKind
from docguard.parsers.code_javascript import parse_source

SAMPLE = '''
/** Adds two numbers. */
function add(a, b = 1) {
  return a + b;
}

export const mul = (x, y = 2) => x * y;

/**
 * A geometric shape.
 */
class Shape {
  /** Area at a scale. */
  area(scale = 1) {
    return scale;
  }
  static make(n) {
    return n;
  }
}

const noop = () => {};
'''


def _by_qual(source, path="a.js"):
    return {(u.qualified_name, u.kind): u for u in parse_source(source, path)}


def test_extraction():
    units = {u.qualified_name: u for u in parse_source(SAMPLE, "a.js")}

    assert units["add"].kind is CodeUnitKind.FUNCTION
    assert units["add"].docstring == "Adds two numbers."
    assert [(p.name, p.default) for p in units["add"].params] == [("a", None), ("b", "1")]
    assert units["add"].signature == "(a, b = 1)"

    # arrow-function assignment
    assert units["mul"].kind is CodeUnitKind.FUNCTION
    assert [(p.name, p.default) for p in units["mul"].params] == [("x", None), ("y", "2")]

    # class + methods
    assert units["Shape"].kind is CodeUnitKind.CLASS
    assert units["Shape"].signature == ""
    assert units["Shape.area"].kind is CodeUnitKind.METHOD
    assert units["Shape.area"].docstring == "Area at a scale."
    assert [(p.name, p.default) for p in units["Shape.area"].params] == [("scale", "1")]
    assert "Shape" in units["Shape.area"].symbols
    assert units["Shape.make"].qualified_name == "Shape.make"

    # zero-arg arrow still extracted
    assert units["noop"].params == []


def test_param_rename_and_signature_change():
    old = _by_qual("function add(a, b = 1) { return a + b; }")
    new = _by_qual("function add(a, total = 1) { return a + total; }")
    key = ("add", CodeUnitKind.FUNCTION)
    impact = classify_change(old[key], new[key])
    assert impact is not None
    assert ChangeKind.PARAM_RENAMED in impact.change_kinds
    assert ChangeKind.SIGNATURE_CHANGE in impact.change_kinds


def test_default_changed():
    old = _by_qual("export const mul = (x, y = 2) => x * y;")
    new = _by_qual("export const mul = (x, y = 5) => x * y;")
    key = ("mul", CodeUnitKind.FUNCTION)
    impact = classify_change(old[key], new[key])
    assert impact is not None
    assert ChangeKind.DEFAULT_CHANGED in impact.change_kinds
