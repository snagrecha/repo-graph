"""Tests for the Python language parser."""

from __future__ import annotations

import textwrap

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from codenexus.graph.schema import EdgeType, NodeType, make_node_id
from codenexus.ingestion.languages.python import PythonParser

_PARSER = Parser(Language(tspython.language()))
_EXTRACTOR = PythonParser()
_ROOT = "/repo"
_FILE = "/repo/src/mod.py"


def _parse(src: str):
    tree = _PARSER.parse(textwrap.dedent(src).encode())
    return _EXTRACTOR.extract_nodes_and_edges(tree, _FILE, _ROOT)


# ---------------------------------------------------------------------------
# File node
# ---------------------------------------------------------------------------


def test_file_node_created():
    nodes, _ = _parse("x = 1\n")
    file_nodes = [n for n in nodes if n.type == NodeType.FILE]
    assert len(file_nodes) == 1
    assert file_nodes[0].name == "mod.py"
    assert file_nodes[0].language == "python"
    assert file_nodes[0].id == make_node_id(_ROOT, _FILE, "")


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------


def test_top_level_function():
    nodes, edges = _parse("""\
        def foo(x):
            return x + 1
        """)
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert len(func_nodes) == 1
    fn = func_nodes[0]
    assert fn.name == "foo"
    assert fn.language == "python"
    assert fn.start_line == 1
    assert fn.end_line == 2
    assert fn.id == make_node_id(_ROOT, _FILE, "foo")


def test_function_contains_edge():
    nodes, edges = _parse("def foo(): pass\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    fn_id = make_node_id(_ROOT, _FILE, "foo")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == fn_id for e in contains)


def test_decorated_function():
    nodes, edges = _parse("""\
        @property
        def foo(self):
            return self._x
        """)
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert len(func_nodes) == 1
    assert func_nodes[0].name == "foo"


def test_multiple_functions():
    nodes, _ = _parse("def a(): pass\ndef b(): pass\ndef c(): pass\n")
    names = {n.name for n in nodes if n.type == NodeType.FUNCTION}
    assert names == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------


def test_top_level_class():
    nodes, edges = _parse("""\
        class MyClass:
            def method(self): pass
        """)
    class_nodes = [n for n in nodes if n.type == NodeType.CLASS]
    assert len(class_nodes) == 1
    cls = class_nodes[0]
    assert cls.name == "MyClass"
    assert cls.start_line == 1


def test_class_contains_edge():
    nodes, edges = _parse("class Foo: pass\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    cls_id = make_node_id(_ROOT, _FILE, "Foo")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == cls_id for e in contains)


def test_class_inherits_edge():
    nodes, edges = _parse("""\
        class Base:
            pass

        class Child(Base):
            pass
        """)
    inherits = [e for e in edges if e.type == EdgeType.INHERITS]
    child_id = make_node_id(_ROOT, _FILE, "Child")
    base_id = make_node_id(_ROOT, _FILE, "Base")
    assert any(e.source_id == child_id and e.target_id == base_id for e in inherits)


def test_decorated_class():
    nodes, _ = _parse("@dataclass\nclass Foo:\n    x: int\n")
    class_nodes = [n for n in nodes if n.type == NodeType.CLASS]
    assert len(class_nodes) == 1
    assert class_nodes[0].name == "Foo"


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


def test_uppercase_constant_is_symbol():
    nodes, edges = _parse("TOP_CONST = 42\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert len(syms) == 1
    assert syms[0].name == "TOP_CONST"


def test_lowercase_assignment_not_extracted():
    nodes, _ = _parse("local_var = 1\nsome_val = 'x'\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert syms == []


def test_underscore_prefixed_symbol_not_extracted():
    nodes, _ = _parse("_INTERNAL = 1\n__ALL__ = 2\n")
    syms = [n for n in nodes if n.type == NodeType.SYMBOL]
    assert syms == []


def test_symbol_contains_edge():
    nodes, edges = _parse("MAX_RETRIES = 5\n")
    file_id = make_node_id(_ROOT, _FILE, "")
    sym_id = make_node_id(_ROOT, _FILE, "MAX_RETRIES")
    contains = [e for e in edges if e.type == EdgeType.CONTAINS]
    assert any(e.source_id == file_id and e.target_id == sym_id for e in contains)


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


def test_intra_file_call_edge():
    nodes, edges = _parse("""\
        def helper():
            pass

        def caller():
            helper()
        """)
    helper_id = make_node_id(_ROOT, _FILE, "helper")
    caller_id = make_node_id(_ROOT, _FILE, "caller")
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert any(e.source_id == caller_id and e.target_id == helper_id for e in call_edges)


def test_no_self_call_edge():
    nodes, edges = _parse("""\
        def recursive():
            recursive()
        """)
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert call_edges == []


def test_unknown_callee_not_added():
    nodes, edges = _parse("""\
        def foo():
            external_lib()
        """)
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert call_edges == []


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


def test_relative_import_edge(tmp_path):
    utils = tmp_path / "utils.py"
    utils.write_text("def helper(): pass\n")
    caller = str(tmp_path / "mod.py")
    root = str(tmp_path)

    src = "from .utils import helper\n"
    tree = _PARSER.parse(src.encode())
    nodes, edges = _EXTRACTOR.extract_nodes_and_edges(tree, caller, root)

    file_id = make_node_id(root, caller, "")
    target_id = make_node_id(root, str(utils), "")
    import_edges = [e for e in edges if e.type == EdgeType.IMPORTS]
    assert any(e.source_id == file_id and e.target_id == target_id for e in import_edges)


def test_stdlib_import_no_edge():
    nodes, edges = _parse("import os\nimport sys\nfrom pathlib import Path\n")
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


def test_nested_class_not_extracted():
    nodes, _ = _parse("""\
        class Outer:
            class Inner:
                pass
        """)
    class_nodes = [n for n in nodes if n.type == NodeType.CLASS]
    # Only top-level Outer; Inner is nested so excluded
    assert len(class_nodes) == 1
    assert class_nodes[0].name == "Outer"


def test_nested_function_not_extracted():
    nodes, _ = _parse("""\
        def outer():
            def inner():
                pass
        """)
    func_nodes = [n for n in nodes if n.type == NodeType.FUNCTION]
    assert len(func_nodes) == 1
    assert func_nodes[0].name == "outer"
