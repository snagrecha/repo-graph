"""Tests for the TypeScript language parser."""

from __future__ import annotations

import textwrap

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from codenexus.graph.schema import EdgeType, NodeType, make_node_id
from codenexus.ingestion.languages.typescript import TypeScriptParser

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
    nodes, _ = _parse("export function a() {}\nexport function b() {}\nfunction c() {}\n")
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
    assert any(e.source_id == caller_id and e.target_id == helper_id for e in call_edges)


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
    assert any(e.source_id == caller_id and e.target_id == helper_id for e in call_edges)


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
    assert any(e.source_id == file_id and e.target_id == target_id for e in import_edges)


def test_third_party_import_no_edge():
    nodes, edges = _parse("import React from 'react';\nimport { useState } from 'react';\n")
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


# ---------------------------------------------------------------------------
# Interface extraction
# ---------------------------------------------------------------------------


def test_interface_extracted():
    nodes, _ = _parse("interface CandidateItem { id: number; name: string; }\n")
    iface_nodes = [n for n in nodes if n.type == NodeType.INTERFACE]
    assert len(iface_nodes) == 1
    assert iface_nodes[0].name == "CandidateItem"
    assert iface_nodes[0].id == make_node_id(_ROOT, _FILE, "CandidateItem")


def test_exported_interface_extracted():
    nodes, _ = _parse("export interface ArticleOut { title: string; }\n")
    iface_nodes = [n for n in nodes if n.type == NodeType.INTERFACE]
    assert len(iface_nodes) == 1
    assert iface_nodes[0].name == "ArticleOut"


def test_interface_contains_edge():
    nodes, edges = _parse("interface Foo { x: number; }\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    iface_id = make_node_id(_ROOT, _FILE, "Foo")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == iface_id for e in contains)


# ---------------------------------------------------------------------------
# Type alias extraction
# ---------------------------------------------------------------------------


def test_type_alias_extracted():
    nodes, _ = _parse("type CandidateGrid = CandidateItem[];\n")
    type_nodes = [n for n in nodes if n.type == NodeType.TYPE_ALIAS]
    assert len(type_nodes) == 1
    assert type_nodes[0].name == "CandidateGrid"


def test_exported_type_alias_extracted():
    nodes, _ = _parse("export type Status = 'active' | 'inactive';\n")
    type_nodes = [n for n in nodes if n.type == NodeType.TYPE_ALIAS]
    assert len(type_nodes) == 1
    assert type_nodes[0].name == "Status"


def test_type_alias_contains_edge():
    nodes, edges = _parse("type MyType = string | number;\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    type_id = make_node_id(_ROOT, _FILE, "MyType")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == type_id for e in contains)


# ---------------------------------------------------------------------------
# Enum extraction
# ---------------------------------------------------------------------------


def test_enum_extracted_as_symbol():
    nodes, _ = _parse("enum Direction { Up, Down, Left, Right }\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL and n.name == "Direction"]
    assert len(syms) == 1


def test_exported_enum_extracted():
    nodes, _ = _parse("export enum Status { Active = 'active', Inactive = 'inactive' }\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL and n.name == "Status"]
    assert len(syms) == 1


# ---------------------------------------------------------------------------
# PascalCase export const (React components, styled-components, etc.)
# ---------------------------------------------------------------------------


def test_pascalcase_export_const_extracted_as_symbol():
    nodes, _ = _parse("export const CandidateGrid = styled.div`display: grid;`;\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL and n.name == "CandidateGrid"]
    assert len(syms) == 1


def test_pascalcase_non_export_const_extracted():
    nodes, _ = _parse("const MyContext = createContext(null);\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL and n.name == "MyContext"]
    assert len(syms) == 1


def test_camelcase_const_not_extracted_as_symbol():
    nodes, _ = _parse("const myVar = getValue();\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL and n.name == "myVar"]
    assert syms == []


def test_pascalcase_arrow_function_extracted_as_function_not_symbol():
    nodes, _ = _parse("export const MyComponent = () => null;\n")
    funcs = [n for n in nodes if n.type == NodeType.FUNCTION and n.name == "MyComponent"]
    syms = [n for n in nodes if n.type == NodeType.SYMBOL and n.name == "MyComponent"]
    assert len(funcs) == 1
    assert syms == []


# ---------------------------------------------------------------------------
# Member access / accessed_fields metadata
# ---------------------------------------------------------------------------


def test_member_accesses_stored_in_metadata():
    nodes, _ = _parse("function render(item) { return item.name + item.certifications.length; }\n")
    fn = next(n for n in nodes if n.type == NodeType.FUNCTION and n.name == "render")
    assert "accessed_fields" in fn.metadata
    assert "name" in fn.metadata["accessed_fields"]
    assert "certifications" in fn.metadata["accessed_fields"]


def test_member_access_line_numbers_recorded():
    src = "function show(x) {\n  return x.status;\n}\n"
    nodes, _ = _parse(src)
    fn = next(n for n in nodes if n.type == NodeType.FUNCTION and n.name == "show")
    assert fn.metadata["accessed_fields"]["status"] == [2]


def test_member_accesses_deduplicated_per_line():
    src = "function f(a) { return a.x + a.x + a.x; }\n"
    nodes, _ = _parse(src)
    fn = next(n for n in nodes if n.type == NodeType.FUNCTION and n.name == "f")
    assert fn.metadata["accessed_fields"]["x"] == [1]


def test_function_with_no_member_accesses_has_no_accessed_fields():
    nodes, _ = _parse("function pure(a, b) { return a + b; }\n")
    fn = next(n for n in nodes if n.type == NodeType.FUNCTION and n.name == "pure")
    assert "accessed_fields" not in fn.metadata


def test_arrow_function_member_accesses():
    nodes, _ = _parse("const getLabel = (item) => item.label;\n")
    fn = next(n for n in nodes if n.type == NodeType.FUNCTION and n.name == "getLabel")
    assert "label" in fn.metadata.get("accessed_fields", {})


# ---------------------------------------------------------------------------
# JSX CALLS edges (TSX parser only)
# ---------------------------------------------------------------------------

_TSX_PARSER_INST = Parser(Language(tsts.language_tsx()))
_TSX_EXTRACTOR = TypeScriptParser(tsx=True)
_TSX_FILE = "/repo/src/mod.tsx"


def _parse_tsx(src: str):
    tree = _TSX_PARSER_INST.parse(textwrap.dedent(src).encode())
    return _TSX_EXTRACTOR.extract_nodes_and_edges(tree, _TSX_FILE, _ROOT)


def test_jsx_self_closing_element_creates_calls_edge():
    # <Button /> should create a CALLS edge from Page to Button
    src = "function Button() { return null; }\nfunction Page() { return <Button />; }\n"
    _, edges = _parse_tsx(src)
    button_id = make_node_id(_ROOT, _TSX_FILE, "Button")
    page_id = make_node_id(_ROOT, _TSX_FILE, "Page")
    calls = [e for e in edges if e.type == EdgeType.CALLS]
    assert any(e.source_id == page_id and e.target_id == button_id for e in calls)


def test_jsx_opening_element_creates_calls_edge():
    # <Card>...</Card> should create a CALLS edge from List to Card
    src = "function Card() { return null; }\n" "function List() { return <Card></Card>; }\n"
    _, edges = _parse_tsx(src)
    card_id = make_node_id(_ROOT, _TSX_FILE, "Card")
    list_id = make_node_id(_ROOT, _TSX_FILE, "List")
    calls = [e for e in edges if e.type == EdgeType.CALLS]
    assert any(e.source_id == list_id and e.target_id == card_id for e in calls)


def test_html_intrinsic_jsx_does_not_create_edge():
    # <div />, <span> are lowercase HTML intrinsics — no edge expected
    src = "function Page() { return <div><span>hello</span></div>; }\n"
    _, edges = _parse_tsx(src)
    calls = [e for e in edges if e.type == EdgeType.CALLS]
    assert calls == []


def test_jsx_component_not_in_file_does_not_create_edge():
    # <ExternalComponent /> is not defined in this file — no edge expected
    src = "function Page() { return <ExternalComponent />; }\n"
    _, edges = _parse_tsx(src)
    calls = [e for e in edges if e.type == EdgeType.CALLS]
    assert calls == []


def test_ts_parser_does_not_have_jsx_query():
    # The plain TS parser must not process JSX elements
    assert _EXTRACTOR._jsx_query is None
