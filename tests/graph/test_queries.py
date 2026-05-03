from codenexus.graph.queries import get_downstream_deps, get_upstream_callers
from codenexus.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id


def _node(name: str, file_path: str = "test.py") -> Node:
    return Node(
        id=make_node_id("/repo", file_path, name),
        type=NodeType.FUNCTION,
        name=name,
        file_path=file_path,
        language="python",
    )


def _edge(src: Node, tgt: Node, etype: EdgeType = EdgeType.CALLS) -> Edge:
    return Edge(source_id=src.id, target_id=tgt.id, type=etype)


# ------------------------------------------------------------------
# get_downstream_deps
# ------------------------------------------------------------------


def test_downstream_depth_1(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.add_edge(_edge(b, c))

    deps = get_downstream_deps(tmp_store, a.id, max_depth=1)
    assert {n.name for n in deps} == {"b"}


def test_downstream_depth_2(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.add_edge(_edge(b, c))

    deps = get_downstream_deps(tmp_store, a.id, max_depth=2)
    assert {n.name for n in deps} == {"b", "c"}


def test_downstream_transitive_chain(tmp_store):
    nodes = [_node(name) for name in ["a", "b", "c", "d"]]
    for n in nodes:
        tmp_store.add_node(n)
    for i in range(len(nodes) - 1):
        tmp_store.add_edge(_edge(nodes[i], nodes[i + 1]))

    deps = get_downstream_deps(tmp_store, nodes[0].id, max_depth=10)
    assert {n.name for n in deps} == {"b", "c", "d"}


def test_downstream_empty_when_no_outgoing(tmp_store):
    a = _node("a")
    tmp_store.add_node(a)
    assert get_downstream_deps(tmp_store, a.id) == []


def test_downstream_nonexistent_node(tmp_store):
    assert get_downstream_deps(tmp_store, "ghost") == []


def test_downstream_cycle_terminates(tmp_store):
    a, b = _node("a"), _node("b")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.add_edge(_edge(b, a))

    deps = get_downstream_deps(tmp_store, a.id, max_depth=10)
    assert len(deps) == 1
    assert deps[0].name == "b"


def test_downstream_diamond(tmp_store):
    # a -> b, a -> c, b -> d, c -> d
    a, b, c, d = _node("a"), _node("b"), _node("c"), _node("d")
    for n in [a, b, c, d]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.add_edge(_edge(a, c))
    tmp_store.add_edge(_edge(b, d))
    tmp_store.add_edge(_edge(c, d))

    deps = get_downstream_deps(tmp_store, a.id, max_depth=3)
    # d should appear exactly once despite two paths to it
    names = [n.name for n in deps]
    assert names.count("d") == 1
    assert set(names) == {"b", "c", "d"}


def test_downstream_edge_type_filter(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, b, EdgeType.CALLS))
    tmp_store.add_edge(_edge(a, c, EdgeType.IMPORTS))

    deps = get_downstream_deps(tmp_store, a.id, edge_types={EdgeType.CALLS})
    assert {n.name for n in deps} == {"b"}


def test_downstream_multiple_edge_types_in_filter(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, b, EdgeType.CALLS))
    tmp_store.add_edge(_edge(a, c, EdgeType.IMPORTS))

    deps = get_downstream_deps(
        tmp_store, a.id, edge_types={EdgeType.CALLS, EdgeType.IMPORTS}
    )
    assert {n.name for n in deps} == {"b", "c"}


# ------------------------------------------------------------------
# get_upstream_callers
# ------------------------------------------------------------------


def test_upstream_direct_callers(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, c))
    tmp_store.add_edge(_edge(b, c))

    callers = get_upstream_callers(tmp_store, c.id, max_depth=1)
    assert {n.name for n in callers} == {"a", "b"}


def test_upstream_transitive(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.add_edge(_edge(b, c))

    callers = get_upstream_callers(tmp_store, c.id, max_depth=2)
    assert {n.name for n in callers} == {"a", "b"}


def test_upstream_empty_when_no_incoming(tmp_store):
    a = _node("a")
    tmp_store.add_node(a)
    assert get_upstream_callers(tmp_store, a.id) == []


def test_upstream_nonexistent_node(tmp_store):
    assert get_upstream_callers(tmp_store, "ghost") == []


def test_upstream_cycle_terminates(tmp_store):
    a, b = _node("a"), _node("b")
    tmp_store.add_node(a)
    tmp_store.add_node(b)
    tmp_store.add_edge(_edge(a, b))
    tmp_store.add_edge(_edge(b, a))

    callers = get_upstream_callers(tmp_store, b.id, max_depth=10)
    assert len(callers) == 1
    assert callers[0].name == "a"


def test_upstream_edge_type_filter(tmp_store):
    a, b, c = _node("a"), _node("b"), _node("c")
    for n in [a, b, c]:
        tmp_store.add_node(n)
    tmp_store.add_edge(_edge(a, c, EdgeType.CALLS))
    tmp_store.add_edge(_edge(b, c, EdgeType.IMPORTS))

    callers = get_upstream_callers(tmp_store, c.id, edge_types={EdgeType.CALLS})
    assert {n.name for n in callers} == {"a"}
