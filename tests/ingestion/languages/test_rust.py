"""Tests for the Rust language parser."""

from __future__ import annotations

import textwrap

import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser

from repo_lens.graph.schema import EdgeType, NodeType, make_node_id
from repo_lens.ingestion.languages.rust import RustParser

_RS_PARSER = Parser(Language(tsrust.language()))
_EXTRACTOR = RustParser()
_ROOT = "/repo"
_FILE = "/repo/src/lib.rs"


def _parse(src: str):
    tree = _RS_PARSER.parse(textwrap.dedent(src).encode())
    return _EXTRACTOR.extract_nodes_and_edges(tree, _FILE, _ROOT)


# ---------------------------------------------------------------------------
# File node
# ---------------------------------------------------------------------------


def test_file_node_created():
    nodes, _ = _parse("pub const X: u32 = 1;\n")
    file_nodes = [n for n in nodes if n.type == NodeType.FILE]
    assert len(file_nodes) == 1
    assert file_nodes[0].name == "lib.rs"
    assert file_nodes[0].language == "rust"
    assert file_nodes[0].id == make_node_id(_ROOT, _FILE, "")


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------


def test_pub_function():
    nodes, _ = _parse("pub fn top_func(x: u32) -> u32 { x }\n")
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert len(func_nodes) == 1
    fn = func_nodes[0]
    assert fn.name == "top_func"
    assert fn.metadata["pub"] is True


def test_private_function():
    nodes, _ = _parse("fn private_func() {}\n")
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert len(func_nodes) == 1
    assert func_nodes[0].name == "private_func"
    assert func_nodes[0].metadata["pub"] is False


def test_function_contains_edge():
    nodes, edges = _parse("pub fn foo() {}\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    fn_id = make_node_id(_ROOT, _FILE, "foo")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == fn_id for e in contains)


def test_multiple_functions():
    nodes, _ = _parse("pub fn a() {}\npub fn b() {}\nfn c() {}\n")
    names = {n.name for n in nodes if n.type == NodeType.FUNCTION}
    assert names == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Struct / enum extraction
# ---------------------------------------------------------------------------


def test_pub_struct():
    nodes, _ = _parse("pub struct MyStruct { x: u32 }\n")
    class_nodes = [n for n in nodes if n.type == NodeType.CLASS]
    assert len(class_nodes) == 1
    assert class_nodes[0].name == "MyStruct"
    assert class_nodes[0].metadata["pub"] is True


def test_pub_enum():
    nodes, _ = _parse("pub enum Color { Red, Green, Blue }\n")
    class_nodes = [n for n in nodes if n.type == NodeType.CLASS]
    assert len(class_nodes) == 1
    assert class_nodes[0].name == "Color"


def test_struct_contains_edge():
    nodes, edges = _parse("pub struct Foo { x: u32 }\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    struct_id = make_node_id(_ROOT, _FILE, "Foo")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == struct_id for e in contains)


# ---------------------------------------------------------------------------
# Const extraction
# ---------------------------------------------------------------------------


def test_pub_const():
    nodes, _ = _parse("pub const LIMIT: u32 = 100;\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert len(syms) == 1
    assert syms[0].name == "LIMIT"
    assert syms[0].metadata["pub"] is True


def test_private_const():
    nodes, _ = _parse("const INTERNAL: u32 = 0;\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert len(syms) == 1
    assert syms[0].name == "INTERNAL"
    assert syms[0].metadata["pub"] is False


# ---------------------------------------------------------------------------
# impl blocks
# ---------------------------------------------------------------------------


def test_impl_methods_extracted():
    nodes, _ = _parse("""\
        pub struct Foo {}
        impl Foo {
            pub fn method(&self) {}
            fn private_method(&self) {}
        }
        """)
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    names = {n.name for n in func_nodes}
    assert "Foo::method" in names
    assert "Foo::private_method" in names


def test_impl_method_contains_edge():
    nodes, edges = _parse("""\
        pub struct Foo {}
        impl Foo {
            pub fn method(&self) {}
        }
        """)
    file_id = make_node_id(_ROOT, _FILE, "")
    method_id = make_node_id(_ROOT, _FILE, "Foo::method")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == method_id for e in contains)


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


def test_intra_file_call_edge():
    nodes, edges = _parse("""\
        pub fn helper() {}
        pub fn caller() { helper(); }
        """)
    helper_id = make_node_id(_ROOT, _FILE, "helper")
    caller_id = make_node_id(_ROOT, _FILE, "caller")
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert any(
        e.source_id == caller_id and e.target_id == helper_id for e in call_edges
    )


def test_no_self_call_edge():
    nodes, edges = _parse("pub fn recursive() { recursive(); }\n")
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert call_edges == []


def test_external_call_not_added():
    nodes, edges = _parse("pub fn foo() { external_crate::do_thing(); }\n")
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert call_edges == []


# ---------------------------------------------------------------------------
# Imports (use declarations)
# ---------------------------------------------------------------------------


def test_crate_relative_import_edge(tmp_path):
    # Create src/utils.rs so the resolver can find it
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    utils = src_dir / "utils.rs"
    utils.write_text("pub fn helper() {}\n")
    lib_rs = str(src_dir / "lib.rs")
    root = str(tmp_path)

    src = "use crate::utils::helper;\n"
    tree = _RS_PARSER.parse(src.encode())
    nodes, edges = _EXTRACTOR.extract_nodes_and_edges(tree, lib_rs, root)

    file_id = make_node_id(root, lib_rs, "")
    target_id = make_node_id(root, str(utils), "")
    import_edges = [e for e in edges if e.type == EdgeType.IMPORTS]
    assert any(
        e.source_id == file_id and e.target_id == target_id for e in import_edges
    )


def test_std_import_no_edge():
    nodes, edges = _parse("use std::collections::HashMap;\nuse std::io::Write;\n")
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
