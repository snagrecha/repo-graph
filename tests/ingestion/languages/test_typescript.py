"""Tests for the TypeScript language parser."""

from __future__ import annotations

import textwrap

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from repo_graph.graph.schema import EdgeType, NodeType, make_node_id
from repo_graph.ingestion.languages.typescript import TypeScriptParser

_TS_PARSER = Parser(Language(tsts.language_typescript()))
_EXTRACTOR = TypeScriptParser(tsx=False)
_ROOT = "/repo"
_FILE = "/repo/src/mod.ts"


def _parse(src: str):
    tree = _TS_PARSER.parse(textwrap.dedent(src).encode())
    return _EXTRACTOR.extract_nodes_and_edges(tree, _FILE, _ROOT)


# ---------------------------------------------------------------------------
# File node
# ---------------------------------------------------------------------------


def test_file_node_created():
    nodes, _ = _parse("const x = 1;\n")
    file_nodes = [n for n in nodes if n.type == NodeType.FILE]
    assert len(file_nodes) == 1
    assert file_nodes[0].name == "mod.ts"
    assert file_nodes[0].language == "typescript"
    assert file_nodes[0].id == make_node_id(_ROOT, _FILE, "")


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------


def test_exported_function():
    nodes, _ = _parse("export function topFunc(x: number): string { return ''; }\n")
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert len(func_nodes) == 1
    fn = func_nodes[0]
    assert fn.name == "topFunc"
    assert fn.id == make_node_id(_ROOT, _FILE, "topFunc")


def test_non_exported_function():
    nodes, _ = _parse("function privateFunc() {}\n")
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert len(func_nodes) == 1
    assert func_nodes[0].name == "privateFunc"


def test_function_contains_edge():
    nodes, edges = _parse("export function foo() {}\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    fn_id = make_node_id(_ROOT, _FILE, "foo")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == fn_id for e in contains)


def test_multiple_functions():
    nodes, _ = _parse(
        "export function a() {}\nexport function b() {}\nfunction c() {}\n"
    )
    names = {n.name for n in nodes if n.type == NodeType.FUNCTION}
    assert names == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------


def test_exported_class():
    nodes, _ = _parse("export class MyClass {}\n")
    class_nodes = [n for n in nodes if n.type == NodeType.CLASS]
    assert len(class_nodes) == 1
    assert class_nodes[0].name == "MyClass"


def test_non_exported_class():
    nodes, _ = _parse("class Private {}\n")
    class_nodes = [n for n in nodes if n.type == NodeType.CLASS]
    assert len(class_nodes) == 1
    assert class_nodes[0].name == "Private"


def test_class_inherits_edge():
    nodes, edges = _parse("""\
        class Base {}
        export class Child extends Base {}
        """)
    child_id = make_node_id(_ROOT, _FILE, "Child")
    base_id = make_node_id(_ROOT, _FILE, "Base")
    inherits = [e for e in edges if e.type == EdgeType.INHERITS]
    assert any(e.source_id == child_id and e.target_id == base_id for e in inherits)


def test_class_contains_edge():
    nodes, edges = _parse("export class Foo {}\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    cls_id = make_node_id(_ROOT, _FILE, "Foo")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == cls_id for e in contains)


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


def test_exported_uppercase_const_is_symbol():
    nodes, _ = _parse("export const MAX_SIZE = 100;\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert len(syms) == 1
    assert syms[0].name == "MAX_SIZE"


def test_lowercase_const_not_extracted():
    nodes, _ = _parse("export const myVar = 'hello';\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert syms == []


def test_underscore_prefixed_symbol_not_extracted():
    nodes, _ = _parse("export const _INTERNAL = 1;\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert syms == []


def test_symbol_contains_edge():
    nodes, edges = _parse("export const API_URL = 'https://example.com';\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    sym_id = make_node_id(_ROOT, _FILE, "API_URL")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == sym_id for e in contains)


# ---------------------------------------------------------------------------
# Arrow functions
# ---------------------------------------------------------------------------


def test_arrow_function_extracted_as_function():
    nodes, _ = _parse("const greet = () => {};\n")
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert any(n.name == "greet" for n in func_nodes)


def test_exported_arrow_function_extracted():
    nodes, _ = _parse("export const handler = (x: number) => x * 2;\n")
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert any(n.name == "handler" for n in func_nodes)


def test_arrow_function_not_extracted_as_symbol():
    nodes, _ = _parse("const greet = () => {};\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert not any(n.name == "greet" for n in syms)


def test_arrow_function_contains_edge():
    nodes, edges = _parse("const fn = () => {};\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    fn_id = make_node_id(_ROOT, _FILE, "fn")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == fn_id for e in contains)


def test_arrow_function_call_edge():
    nodes, edges = _parse("function helper() {}\nconst caller = () => { helper(); };\n")
    helper_id = make_node_id(_ROOT, _FILE, "helper")
    caller_id = make_node_id(_ROOT, _FILE, "caller")
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert any(
        e.source_id == caller_id and e.target_id == helper_id for e in call_edges
    )


def test_underscore_arrow_function_not_extracted():
    nodes, _ = _parse("const _internal = () => {};\n")
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert not any(n.name == "_internal" for n in func_nodes)


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


def test_intra_file_call_edge():
    nodes, edges = _parse("""\
        function helper() {}
        export function caller() { helper(); }
        """)
    helper_id = make_node_id(_ROOT, _FILE, "helper")
    caller_id = make_node_id(_ROOT, _FILE, "caller")
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert any(
        e.source_id == caller_id and e.target_id == helper_id for e in call_edges
    )


def test_no_self_call_edge():
    nodes, edges = _parse("function recursive() { recursive(); }\n")
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert call_edges == []


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


def test_relative_import_edge(tmp_path):
    utils = tmp_path / "utils.ts"
    utils.write_text("export function helper() {}\n")
    caller = str(tmp_path / "mod.ts")
    root = str(tmp_path)

    src = "import { helper } from './utils';\n"
    tree = _TS_PARSER.parse(src.encode())
    nodes, edges = _EXTRACTOR.extract_nodes_and_edges(tree, caller, root)

    file_id = make_node_id(root, caller, "")
    target_id = make_node_id(root, str(utils), "")
    import_edges = [e for e in edges if e.type == EdgeType.IMPORTS]
    assert any(
        e.source_id == file_id and e.target_id == target_id for e in import_edges
    )


def test_third_party_import_no_edge():
    nodes, edges = _parse(
        "import React from 'react';\nimport { useState } from 'react';\n"
    )
    import_edges = [e for e in edges if e.type == EdgeType.IMPORTS]
    assert import_edges == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_file():
    nodes, edges = _parse("")
    file_nodes = [n for n in nodes if n.type == NodeType.FILE]
    assert len(file_nodes) == 1
    assert edges == []
