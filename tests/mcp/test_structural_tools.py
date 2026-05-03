from codenexus.graph.schema import Node, NodeType, make_node_id
from codenexus.mcp.tools import structural


def _make_node(name, file_path, node_type=NodeType.FUNCTION, start_line=1, end_line=10):
    return Node(
        id=make_node_id("/repo", file_path, name),
        type=node_type,
        name=name,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language="python",
        metadata={},
    )


def test_search_nodes_returns_qualified_name(tmp_store):
    tmp_store.add_node(_make_node("my_func", "src/main.py"))
    results = structural.search_nodes(tmp_store, query="my_func")
    assert len(results) == 1
    assert results[0]["name"] == "my_func"
    assert results[0]["type"] == "function"
    assert results[0]["qualified_name"] == "src/main.py::my_func"


def test_search_nodes_file_path_filter(tmp_store):
    tmp_store.add_node(_make_node("fn_a", "frontend/page.tsx"))
    tmp_store.add_node(_make_node("fn_b", "backend/api.py"))
    results = structural.search_nodes(tmp_store, query="fn", file_path="frontend")
    assert len(results) == 1
    assert results[0]["name"] == "fn_a"


def test_search_nodes_includes_line_numbers(tmp_store):
    tmp_store.add_node(_make_node("my_func", "src/main.py", start_line=5, end_line=15))
    results = structural.search_nodes(tmp_store, query="my_func")
    assert results[0]["start_line"] == 5
    assert results[0]["end_line"] == 15


def test_get_node_signature_uses_end_line(tmp_store, tmp_path):
    repo_root = tmp_path
    src_file = repo_root / "src" / "main.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("def my_func():\n    x = 1\n    return x\n")

    node = Node(
        id="test-id",
        type=NodeType.FUNCTION,
        name="my_func",
        file_path="src/main.py",
        start_line=1,
        end_line=3,
        language="python",
        metadata={},
    )
    tmp_store.add_node(node)

    result = structural.get_node_signature(tmp_store, str(repo_root), "test-id")
    assert result is not None
    assert "def my_func():" in result["signature_snippet"]
    assert "return x" in result["signature_snippet"]
    assert result["qualified_name"] == "src/main.py::my_func"


def test_get_node_signature_falls_back_to_snippet_lines_when_no_end_line(tmp_store, tmp_path):
    repo_root = tmp_path
    src_file = repo_root / "src" / "big.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("\n".join(f"line_{i}" for i in range(50)) + "\n")

    node = Node(
        id="test-id",
        type=NodeType.FUNCTION,
        name="fn",
        file_path="src/big.py",
        start_line=1,
        end_line=None,
        language="python",
        metadata={},
    )
    tmp_store.add_node(node)

    result = structural.get_node_signature(tmp_store, str(repo_root), "test-id", snippet_lines=5)
    assert result is not None
    lines = result["signature_snippet"].splitlines()
    assert len(lines) == 5


def test_get_file_symbols_returns_non_file_nodes(tmp_store):
    file_node = Node(
        id=make_node_id("/repo", "src/mod.py", ""),
        type=NodeType.FILE,
        name="mod.py",
        file_path="src/mod.py",
        start_line=1,
        end_line=30,
        language="python",
        metadata={},
    )
    func_node = _make_node("my_func", "src/mod.py", start_line=5, end_line=10)
    cls_node = _make_node(
        "MyClass", "src/mod.py", node_type=NodeType.CLASS, start_line=15, end_line=25
    )
    other_node = _make_node("other_func", "src/other.py")

    for n in [file_node, func_node, cls_node, other_node]:
        tmp_store.add_node(n)

    results = structural.get_file_symbols(tmp_store, "src/mod.py")
    names = {r["name"] for r in results}
    assert names == {"my_func", "MyClass"}
    assert "mod.py" not in names
    assert "other_func" not in names


def test_get_file_symbols_sorted_by_start_line(tmp_store):
    a = _make_node("z_func", "src/mod.py", start_line=20, end_line=25)
    b = _make_node("a_func", "src/mod.py", start_line=5, end_line=10)
    for n in [a, b]:
        tmp_store.add_node(n)

    results = structural.get_file_symbols(tmp_store, "src/mod.py")
    assert results[0]["name"] == "a_func"
    assert results[1]["name"] == "z_func"


def test_get_file_symbols_empty_for_unknown_file(tmp_store):
    assert structural.get_file_symbols(tmp_store, "does_not_exist.py") == []


def test_search_field_usages_returns_nodes_with_line_numbers(tmp_store):
    node = Node(
        id=make_node_id("/repo", "src/page.tsx", "ImpactedAdvisorsPage"),
        type=NodeType.FUNCTION,
        name="ImpactedAdvisorsPage",
        file_path="src/page.tsx",
        start_line=10,
        end_line=150,
        language="typescript",
        metadata={"accessed_fields": {"certifications": [45, 67], "name": [12]}},
    )
    tmp_store.add_node(node)

    results = structural.search_field_usages(tmp_store, "certifications")
    assert len(results) == 1
    assert results[0]["name"] == "ImpactedAdvisorsPage"
    assert results[0]["qualified_name"] == "src/page.tsx::ImpactedAdvisorsPage"
    assert results[0]["usages_at_lines"] == [45, 67]


def test_search_field_usages_no_match_returns_empty(tmp_store):
    node = Node(
        id=make_node_id("/repo", "src/page.tsx", "Page"),
        type=NodeType.FUNCTION,
        name="Page",
        file_path="src/page.tsx",
        metadata={"accessed_fields": {"name": [5]}},
    )
    tmp_store.add_node(node)
    assert structural.search_field_usages(tmp_store, "nonexistent") == []


def test_search_field_usages_language_filter(tmp_store):
    py_node = Node(
        id=make_node_id("/repo", "api.py", "serialize"),
        type=NodeType.FUNCTION,
        name="serialize",
        file_path="api.py",
        language="python",
        metadata={"accessed_fields": {"certifications": [3]}},
    )
    ts_node = Node(
        id=make_node_id("/repo", "page.tsx", "Page"),
        type=NodeType.FUNCTION,
        name="Page",
        file_path="page.tsx",
        language="typescript",
        metadata={"accessed_fields": {"certifications": [10]}},
    )
    tmp_store.add_node(py_node)
    tmp_store.add_node(ts_node)

    results = structural.search_field_usages(tmp_store, "certifications", language="typescript")
    assert len(results) == 1
    assert results[0]["language"] == "typescript"
