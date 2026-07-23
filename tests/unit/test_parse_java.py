# Neetigya, 2026-07-23: new file — Java extractor tests.
"""Tests for the Java extractor and its change-detection contract."""

from __future__ import annotations

from docguard.changes.classify import classify_change
from docguard.models import ChangeKind, CodeUnitKind
from docguard.parsers.code_java import parse_source

SAMPLE = """
package com.example;

/**
 * A tiny calculator.
 * Adds numbers.
 */
public class Calc {
    private int base;

    public int add(final int a, int b) {
        return a + b + base;
    }

    /** greet someone by name */
    static String greet(String name, int... times) {
        return name;
    }
}

interface Repo {
    List<String> find(@NotNull String id, Map<String, Integer> filters);
}

class Empty {}
"""


def _by_qual(units):
    return {(u.qualified_name, u.kind): u for u in units}


def test_extraction():
    units = parse_source(SAMPLE, "src/Calc.java")
    by = _by_qual(units)

    # classes
    assert ("Calc", CodeUnitKind.CLASS) in by
    assert ("Repo", CodeUnitKind.CLASS) in by
    assert ("Empty", CodeUnitKind.CLASS) in by
    calc = by[("Calc", CodeUnitKind.CLASS)]
    assert calc.name == "Calc"
    assert calc.signature == ""
    assert "tiny calculator" in calc.docstring

    # methods with ClassName.method qualified names
    add = by[("Calc.add", CodeUnitKind.METHOD)]
    assert add.name == "add"
    assert add.kind is CodeUnitKind.METHOD
    assert [p.name for p in add.params] == ["a", "b"]
    assert all(p.default is None for p in add.params)  # Java has no defaults
    assert add.signature == "(final int a, int b)"
    assert "Calc" in add.symbols and "a" in add.symbols and "b" in add.symbols

    greet = by[("Calc.greet", CodeUnitKind.METHOD)]
    assert [p.name for p in greet.params] == ["name", "times"]  # varargs name
    assert "greet someone" in greet.docstring

    # generic types / annotations stripped down to the param name
    find = by[("Repo.find", CodeUnitKind.METHOD)]
    assert [p.name for p in find.params] == ["id", "filters"]


def test_never_raises_on_garbage():
    assert parse_source("this is not java {{{", "x.java") == []
    assert parse_source("", "x.java") == []


NEW = SAMPLE.replace("public int add(final int a, int b)", "public int add(final int x, int b)")


def test_param_rename_detected():
    old = _by_qual(parse_source(SAMPLE, "src/Calc.java"))
    new = _by_qual(parse_source(NEW, "src/Calc.java"))
    key = ("Calc.add", CodeUnitKind.METHOD)
    impact = classify_change(old[key], new[key])
    assert impact is not None
    assert ChangeKind.PARAM_RENAMED in impact.change_kinds
    assert ChangeKind.SIGNATURE_CHANGE in impact.change_kinds
