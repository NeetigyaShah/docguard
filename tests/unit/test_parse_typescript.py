# Neetigya, 2026-07-23: new file — TypeScript extractor tests.
"""TypeScript extractor: structural extraction + change-detection wiring."""

from __future__ import annotations

from docguard.changes.classify import classify_change
from docguard.models import ChangeKind, CodeUnitKind
from docguard.parsers.code_typescript import parse_source

SAMPLE = """
/** Adds two numbers. */
export function add(a: number, b: number = 3): number {
  return a + b;
}

export const mul = (x: number, y = 2): number => x * y;

/** A greeter. */
export class Greeter {
  private name: string;

  /** Greet someone. */
  greet(name: string, loud: boolean = false): string {
    return name;
  }

  static make(this: void, n: string): Greeter {
    return new Greeter();
  }
}

function _internal(...rest: number[]) {}
const { a, b } = obj;
"""


def _by_qual(units):
    return {(u.qualified_name, u.kind): u for u in units}


def test_extraction():
    units = _by_qual(parse_source(SAMPLE, "src/x.ts"))

    add = units[("add", CodeUnitKind.FUNCTION)]
    assert add.name == "add"
    assert [(p.name, p.default) for p in add.params] == [("a", None), ("b", "3")]
    assert add.signature == "(a: number, b: number = 3)"
    assert add.docstring == "Adds two numbers."

    mul = units[("mul", CodeUnitKind.FUNCTION)]
    assert [(p.name, p.default) for p in mul.params] == [("x", None), ("y", "2")]

    greeter = units[("Greeter", CodeUnitKind.CLASS)]
    assert greeter.kind is CodeUnitKind.CLASS
    assert greeter.signature == ""

    greet = units[("Greeter.greet", CodeUnitKind.METHOD)]
    assert greet.name == "greet"
    assert [(p.name, p.default) for p in greet.params] == [("name", None), ("loud", "false")]
    assert greet.docstring == "Greet someone."
    assert "Greeter" in greet.symbols

    # `this` is skipped from method params.
    make = units[("Greeter.make", CodeUnitKind.METHOD)]
    assert [p.name for p in make.params] == ["n"]

    # rest param is named best-effort; destructured `const {a,b}` yields no unit.
    internal = units[("_internal", CodeUnitKind.FUNCTION)]
    assert [p.name for p in internal.params] == ["rest"]
    assert ("a", CodeUnitKind.FUNCTION) not in units


OLD = "export function f(oldName: number, count = 1) { return oldName; }"
NEW = "export function f(newName: number, count = 5) { return newName; }"


def test_change_detection_rename_and_default():
    old = {(u.qualified_name, u.kind): u for u in parse_source(OLD, "src/x.ts")}
    new = {(u.qualified_name, u.kind): u for u in parse_source(NEW, "src/x.ts")}
    key = ("f", CodeUnitKind.FUNCTION)

    impact = classify_change(old[key], new[key])
    assert impact is not None
    kinds = impact.change_kinds
    assert ChangeKind.PARAM_RENAMED in kinds
    assert ChangeKind.SIGNATURE_CHANGE in kinds
    assert ChangeKind.DEFAULT_CHANGED in kinds
