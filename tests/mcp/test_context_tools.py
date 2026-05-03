from codenexus.graph.schema import Node, NodeType
from codenexus.mcp.tools import context


def _make_node(store, node_id, name, file_path, node_type=NodeType.FUNCTION, metadata=None):
    node = Node(
        id=node_id,
        type=node_type,
        name=name,
        file_path=file_path,
        start_line=1,
        end_line=3,
        language="python",
        metadata=metadata or {},
    )
    store.add_node(node)
    return node


def test_get_narrowed_context_returns_target_first(tmp_store, tmp_path):
    store = tmp_store
    repo_root = str(tmp_path)

    # Write a source file
    src = tmp_path / "src" / "calc.py"
    src.parent.mkdir(parents=True)
    src.write_text("def add():\n    return 1\n\n\ndef sub():\n    return -1\n")

    _make_node(store, "n-target", "add", "src/calc.py")
    _make_node(store, "n-a", "sub", "src/calc.py")

    result = context.get_narrowed_context(store, repo_root, "n-target", goal="add numbers")
    assert "target_node" in result
    assert result["target_node"]["id"] == "n-target"
    assert result["snippet_count"] >= 1
    assert result["snippets"][0]["node_id"] == "n-target"
    assert "def add()" in result["snippets"][0]["snippet"]


def test_get_narrowed_context_respects_budget(tmp_store, tmp_path):
    store = tmp_store
    repo_root = str(tmp_path)

    src = tmp_path / "src" / "big.py"
    src.parent.mkdir(parents=True)
    src.write_text("\n".join(f"def fn_{i}():\n    pass" for i in range(20)) + "\n")

    _make_node(store, "n0", "fn_0", "src/big.py")
    for i in range(1, 10):
        _make_node(store, f"n{i}", f"fn_{i}", "src/big.py")

    result = context.get_narrowed_context(store, repo_root, "n0", goal="something", max_tokens=50)
    assert result["used_tokens"] <= 60  # small headroom for target node
    assert result["snippet_count"] <= 3  # target + maybe 1-2 neighbours


def test_get_narrowed_context_unknown_node(tmp_store):
    result = context.get_narrowed_context(tmp_store, "/repo", "nope", goal="x")
    assert "error" in result
