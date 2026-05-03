"""Tests for the top-level parse_file dispatcher."""

from __future__ import annotations

import pytest

from codenexus.graph.schema import NodeType
from codenexus.ingestion.parser import _MAX_FILE_BYTES, LANGUAGE_PARSERS, parse_file


@pytest.fixture()
def repo(tmp_path):
    return tmp_path


# ---------------------------------------------------------------------------
# Language dispatch
# ---------------------------------------------------------------------------


def test_parse_python_file(repo):
    f = repo / "mod.py"
    f.write_text("def foo(): pass\nclass Bar: pass\n")
    result = parse_file(str(f), str(repo))
    assert result is not None
    nodes, edges = result
    types = {n.type for n in nodes}
    assert NodeType.FILE in types
    assert NodeType.FUNCTION in types
    assert NodeType.CLASS in types


def test_parse_typescript_file(repo):
    f = repo / "mod.ts"
    f.write_text("export function greet(): void {}\nexport class Greeter {}\n")
    result = parse_file(str(f), str(repo))
    assert result is not None
    nodes, _ = result
    types = {n.type for n in nodes}
    assert NodeType.FILE in types
    assert NodeType.FUNCTION in types
    assert NodeType.CLASS in types


def test_parse_rust_file(repo):
    f = repo / "lib.rs"
    f.write_text("pub fn hello() {}\npub struct World;\n")
    result = parse_file(str(f), str(repo))
    assert result is not None
    nodes, _ = result
    types = {n.type for n in nodes}
    assert NodeType.FILE in types
    assert NodeType.FUNCTION in types


def test_parse_tsx_file(repo):
    f = repo / "App.tsx"
    f.write_text("export function App(): JSX.Element { return null; }\n")
    result = parse_file(str(f), str(repo))
    assert result is not None
    nodes, _ = result
    assert any(n.type == NodeType.FUNCTION for n in nodes)


def test_parse_js_file(repo):
    f = repo / "index.js"
    f.write_text("function setup() {}\n")
    result = parse_file(str(f), str(repo))
    assert result is not None


# ---------------------------------------------------------------------------
# Unsupported / skip cases
# ---------------------------------------------------------------------------


def test_unsupported_extension_returns_none(repo):
    f = repo / "readme.md"
    f.write_text("# Hello\n")
    assert parse_file(str(f), str(repo)) is None


def test_binary_extension_returns_none(repo):
    f = repo / "image.png"
    f.write_bytes(b"\x89PNG\r\n")
    assert parse_file(str(f), str(repo)) is None


def test_file_too_large_returns_none(repo):
    f = repo / "big.py"
    # Write slightly over 500 KB
    f.write_bytes(b"x = 1\n" * ((_MAX_FILE_BYTES // 6) + 1))
    assert parse_file(str(f), str(repo)) is None


def test_missing_file_returns_none(repo):
    assert parse_file(str(repo / "nonexistent.py"), str(repo)) is None


# ---------------------------------------------------------------------------
# Extension coverage
# ---------------------------------------------------------------------------


def test_language_parsers_covers_expected_extensions():
    expected = {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".mjs",
        ".cjs",
        ".jsx",
        ".rs",
        ".mts",
        ".cts",
    }
    assert expected.issubset(set(LANGUAGE_PARSERS.keys()))


# ---------------------------------------------------------------------------
# Node language field
# ---------------------------------------------------------------------------


def test_python_nodes_have_python_language(repo):
    f = repo / "mod.py"
    f.write_text("def foo(): pass\n")
    nodes, _ = parse_file(str(f), str(repo))
    for n in nodes:
        assert n.language == "python"


def test_rust_nodes_have_rust_language(repo):
    f = repo / "lib.rs"
    f.write_text("pub fn foo() {}\n")
    nodes, _ = parse_file(str(f), str(repo))
    for n in nodes:
        assert n.language == "rust"
