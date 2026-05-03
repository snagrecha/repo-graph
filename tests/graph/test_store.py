import pytest

from codenexus.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id
from codenexus.graph.store import GraphStore


def _node(name: str, file_path: str = "foo.py", node_type: NodeType = NodeType.FUNCTION) -> Node:
    return Node(
        id=make_node_id("/repo", file_path, name),
        type=node_type,
        name=name,
        file_path=file_path,
        start_line=1,
        end_line=10,
        language="python",
    )


def _edge(src: Node, tgt: Node, etype: EdgeType = EdgeType.CALLS, **meta) -> Edge:
    return Edge(source_id=src.id, target_id=tgt.id, type=etype, metadata=meta)


# ------------------------------------------------------------------
# Basic node operations
# ------------------------------------------------------------------


def test_empty_store_counts(tmp_store):
    assert tmp_store.node_count() == 0
    assert tmp_store.edge_count() == 0


def test_add_and_get_node(tmp_store):
    node = _node("my_func")
    tmp_store.add_node(node)
    result = tmp_store.get_node(node.id)
    assert result is not None
    assert result.name == "my_func"
    assert result.type == NodeType.FUNCTION
    assert result.language == "python"


def test_get_nonexistent_node_returns_none(tmp_store):
    assert tmp_store.get_node("does_not_exist") is None


def test_node_count_increments(tmp_store):
    tmp_store.add_node(_node("a"))
    tmp_store.add_node(_node("b"))
    assert tmp_store.node_count() == 2


def test_add_node_upserts_by_id(tmp_store):
    node = _node("fn")
    tmp_store.add_node(node)
    updated = Node(id=node.id, type=NodeType.FUNCTION, name="fn", file_path="foo.py", start_line=99)
    tmp_store.add_node(updated)
    assert tmp_store.node_count() == 1
    assert tmp_store.get_node(node.id).start_line == 99


def test_get_all_nodes(tmp_store):
    a, b = _node("a"), _node("b")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    names = {n.name for n in tmp_store.get_all_nodes()}
    assert names == {"a", "b"}


def test_node_metadata_roundtrip(tmp_store):
    node = Node(
        id=make_node_id("/r", "f.py", "x"),
        type=NodeType.SYMBOL,
        name="x",
        file_path="f.py",
        metadata={"complexity": 7, "tags": ["hot"]},
    )
    tmp_store.add_node(node)
    result = tmp_store.get_node(node.id)
    assert result.metadata == {"complexity": 7, "tags": ["hot"]}


# ------------------------------------------------------------------
# Edge operations
# ------------------------------------------------------------------


def test_add_edge_and_outgoing(tmp_store):
    a, b = _node("a"), _node("b")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b))
    out = tmp_store.get_outgoing_edges(a.id)
    assert len(out) == 1
    assert out[0].target_id == b.id
    assert out[0].type == EdgeType.CALLS


def test_add_edge_and_incoming(tmp_store):
    a, b = _node("a"), _node("b")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b))
    inc = tmp_store.get_incoming_edges(b.id)
    assert len(inc) == 1
    assert inc[0].source_id == a.id


def test_edge_count_increments(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.add_edge(_edge(b, c))
    assert tmp_store.edge_count() == 2


def test_add_edge_missing_source_raises(tmp_store):
    b = _node("b")
    tmp_store.add_node(b)
    with pytest.raises(ValueError, match="Source node"):
        tmp_store.add_edge(Edge(source_id="ghost", target_id=b.id, type=EdgeType.CALLS))


def test_add_edge_missing_target_raises(tmp_store):
    a = _node("a")
    tmp_store.add_node(a)
    with pytest.raises(ValueError, match="Target node"):
        tmp_store.add_edge(Edge(source_id=a.id, target_id="ghost", type=EdgeType.CALLS))


def test_duplicate_edge_upserted(tmp_store):
    a, b = _node("a"), _node("b")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b, count=1))
    tmp_store.add_edge(_edge(a, b, count=2))
    out = tmp_store.get_outgoing_edges(a.id)
    assert len(out) == 1
    assert out[0].metadata["count"] == 2


def test_multiple_edge_types_between_same_nodes(tmp_store):
    a, b = _node("a"), _node("b")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b, EdgeType.CALLS))
    tmp_store.add_edge(_edge(a, b, EdgeType.IMPORTS))
    out = tmp_store.get_outgoing_edges(a.id)
    assert len(out) == 2
    types = {e.type for e in out}
    assert types == {EdgeType.CALLS, EdgeType.IMPORTS}


def test_no_edges_returns_empty_list(tmp_store):
    a = _node("a")
    tmp_store.add_node(a)
    assert tmp_store.get_outgoing_edges(a.id) == []
    assert tmp_store.get_incoming_edges(a.id) == []


def test_edges_for_missing_node_returns_empty(tmp_store):
    assert tmp_store.get_outgoing_edges("nope") == []
    assert tmp_store.get_incoming_edges("nope") == []


# ------------------------------------------------------------------
# delete_nodes_by_file
# ------------------------------------------------------------------


def test_delete_nodes_by_file_removes_nodes(tmp_store):
    a = _node("a", "foo.py")
    b = _node("b", "foo.py")
    c = _node("c", "bar.py")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.delete_nodes_by_file("foo.py")
    assert tmp_store.node_count() == 1
    assert tmp_store.get_node(c.id) is not None
    assert tmp_store.get_node(a.id) is None
    assert tmp_store.get_node(b.id) is None


def test_delete_nodes_by_file_removes_incident_edges(tmp_store):
    a = _node("a", "foo.py")
    b = _node("b", "bar.py")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.delete_nodes_by_file("foo.py")
    assert tmp_store.get_incoming_edges(b.id) == []
    assert tmp_store.edge_count() == 0


def test_delete_nodes_by_file_noop_on_missing(tmp_store):
    a = _node("a", "foo.py")
    tmp_store.add_node(a)
    tmp_store.delete_nodes_by_file("does_not_exist.py")
    assert tmp_store.node_count() == 1


def test_delete_then_readd_nodes(tmp_store):
    a = _node("a", "foo.py")
    b = _node("b", "bar.py")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.delete_nodes_by_file("foo.py")

    # Re-add a fresh version of the deleted node and a new edge
    a2 = _node("a", "foo.py")
    tmp_store.add_node(a2)
    tmp_store.add_edge(_edge(a2, b))
    assert tmp_store.node_count() == 2
    assert tmp_store.edge_count() == 1


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------


def test_persistence_nodes_survive_restart(tmp_path):
    db = tmp_path / "graph.db"
    node = _node("persisted")
    with GraphStore(db) as s:
        s.add_node(node)

    with GraphStore(db) as s2:
        assert s2.node_count() == 1
        assert s2.get_node(node.id).name == "persisted"


def test_persistence_edges_survive_restart(tmp_path):
    db = tmp_path / "graph.db"
    a, b = _node("a"), _node("b")
    with GraphStore(db) as s:
        s.add_node(a)
        s.add_node(b)
        s.add_edge(_edge(a, b))

    with GraphStore(db) as s2:
        assert s2.edge_count() == 1
        out = s2.get_outgoing_edges(a.id)
        assert out[0].target_id == b.id


def test_persistence_graph_traversal_after_restart(tmp_path):
    db = tmp_path / "graph.db"
    a, b, c = _node("a"), _node("b"), _node("c")
    with GraphStore(db) as s:
        for n in [a, b, c]:
            s.add_node(n)
        s.add_edge(_edge(a, b))
        s.add_edge(_edge(b, c))

    with GraphStore(db) as s2:
        # Outgoing from a should reach b; incoming to c should come from b.
        assert {e.target_id for e in s2.get_outgoing_edges(a.id)} == {b.id}
        assert {e.source_id for e in s2.get_incoming_edges(c.id)} == {b.id}


# ------------------------------------------------------------------
# WAL mode
# ------------------------------------------------------------------


def test_wal_mode_is_set(tmp_store):
    row = tmp_store._db.execute("PRAGMA journal_mode").fetchone()
    assert row[0] == "wal"


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------


def test_search_by_name_substring(tmp_store):
    tmp_store.add_node(_node("process_data", "utils.py"))
    tmp_store.add_node(_node("validate_input", "utils.py"))
    tmp_store.add_node(_node("process_output", "output.py"))
    results = tmp_store.search_nodes("process")
    assert {n.name for n in results} == {"process_data", "process_output"}


def test_search_by_file_path(tmp_store):
    tmp_store.add_node(_node("fn_a", "services/auth.py"))
    tmp_store.add_node(_node("fn_b", "services/billing.py"))
    tmp_store.add_node(_node("fn_c", "utils/helpers.py"))
    results = tmp_store.search_nodes("services")
    assert len(results) == 2


def test_search_filtered_by_type(tmp_store):
    tmp_store.add_node(_node("MyClass", node_type=NodeType.CLASS))
    tmp_store.add_node(_node("my_func", node_type=NodeType.FUNCTION))
    results = tmp_store.search_nodes("my", node_type=NodeType.CLASS)
    assert len(results) == 1
    assert results[0].type == NodeType.CLASS


def test_search_filtered_by_language(tmp_store):
    py_node = Node(
        id=make_node_id("/r", "a.py", "fn"),
        type=NodeType.FUNCTION,
        name="fn",
        file_path="a.py",
        language="python",
    )
    ts_node = Node(
        id=make_node_id("/r", "a.ts", "fn"),
        type=NodeType.FUNCTION,
        name="fn",
        file_path="a.ts",
        language="typescript",
    )
    tmp_store.add_node(py_node)
    tmp_store.add_node(ts_node)
    results = tmp_store.search_nodes("fn", language="typescript")
    assert len(results) == 1
    assert results[0].language == "typescript"


def test_search_no_match_returns_empty(tmp_store):
    tmp_store.add_node(_node("my_func"))
    assert tmp_store.search_nodes("zzz_no_match") == []


# ------------------------------------------------------------------
# get_nodes_by_file
# ------------------------------------------------------------------


def test_search_nodes_with_field_access_returns_matching(tmp_store):
    node_with = Node(
        id=make_node_id("/repo", "a.py", "render"),
        type=NodeType.FUNCTION,
        name="render",
        file_path="a.py",
        language="python",
        metadata={"accessed_fields": {"certifications": [10, 25], "name": [5]}},
    )
    node_without = _node("other", "b.py")
    tmp_store.add_node(node_with)
    tmp_store.add_node(node_without)

    results = tmp_store.search_nodes_with_field_access("certifications")
    assert len(results) == 1
    assert results[0].name == "render"


def test_search_nodes_with_field_access_language_filter(tmp_store):
    py_node = Node(
        id=make_node_id("/repo", "a.py", "fn"),
        type=NodeType.FUNCTION,
        name="fn",
        file_path="a.py",
        language="python",
        metadata={"accessed_fields": {"status": [1]}},
    )
    ts_node = Node(
        id=make_node_id("/repo", "b.ts", "fn"),
        type=NodeType.FUNCTION,
        name="fn",
        file_path="b.ts",
        language="typescript",
        metadata={"accessed_fields": {"status": [3]}},
    )
    tmp_store.add_node(py_node)
    tmp_store.add_node(ts_node)

    results = tmp_store.search_nodes_with_field_access("status", language="python")
    assert len(results) == 1
    assert results[0].language == "python"


def test_search_nodes_with_field_access_no_match_returns_empty(tmp_store):
    node = Node(
        id=make_node_id("/repo", "a.py", "fn"),
        type=NodeType.FUNCTION,
        name="fn",
        file_path="a.py",
        metadata={"accessed_fields": {"name": [1]}},
    )
    tmp_store.add_node(node)
    assert tmp_store.search_nodes_with_field_access("nonexistent_field") == []


def test_get_nodes_by_file_returns_matching(tmp_store):
    a = _node("a", "foo.py")
    b = _node("b", "foo.py")
    c = _node("c", "bar.py")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    results = tmp_store.get_nodes_by_file("foo.py")
    assert {n.name for n in results} == {"a", "b"}


def test_get_nodes_by_file_exact_match(tmp_store):
    tmp_store.add_node(_node("fn", "services/auth.py"))
    tmp_store.add_node(_node("fn2", "services/auth_utils.py"))
    results = tmp_store.get_nodes_by_file("services/auth.py")
    assert len(results) == 1
    assert results[0].name == "fn"


def test_get_nodes_by_file_no_match_returns_empty(tmp_store):
    tmp_store.add_node(_node("fn", "foo.py"))
    assert tmp_store.get_nodes_by_file("nonexistent.py") == []


# ------------------------------------------------------------------
# Context manager
# ------------------------------------------------------------------


def test_context_manager_closes_cleanly(tmp_path):
    with GraphStore(tmp_path / "g.db") as s:
        s.add_node(_node("x"))
    # After close, accessing _db should raise (ProgrammingError or similar)
    with pytest.raises(Exception):
        s._db.execute("SELECT 1")
