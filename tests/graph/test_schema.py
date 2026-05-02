from repo_lens.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id


def test_node_type_values():
    assert NodeType.FILE.value == "file"
    assert NodeType.CLASS.value == "class"
    assert NodeType.FUNCTION.value == "function"
    assert NodeType.MODULE.value == "module"
    assert NodeType.SYMBOL.value == "symbol"


def test_edge_type_values():
    assert EdgeType.IMPORTS.value == "imports"
    assert EdgeType.CALLS.value == "calls"
    assert EdgeType.INHERITS.value == "inherits"
    assert EdgeType.CONTAINS.value == "contains"
    assert EdgeType.CO_CHANGES_WITH.value == "co_changes_with"


def test_node_type_is_str_subclass():
    assert isinstance(NodeType.FUNCTION, str)
    assert NodeType.FUNCTION == "function"


def test_edge_type_is_str_subclass():
    assert isinstance(EdgeType.CALLS, str)
    assert EdgeType.CALLS == "calls"


def test_make_node_id_is_deterministic():
    assert make_node_id("/repo", "src/foo.py", "MyClass") == make_node_id(
        "/repo", "src/foo.py", "MyClass"
    )


def test_make_node_id_is_hex_string():
    node_id = make_node_id("/repo", "foo.py", "bar")
    assert len(node_id) == 64
    assert all(c in "0123456789abcdef" for c in node_id)


def test_make_node_id_differs_by_file_path():
    assert make_node_id("/repo", "a.py", "func") != make_node_id(
        "/repo", "b.py", "func"
    )


def test_make_node_id_differs_by_symbol():
    assert make_node_id("/repo", "a.py", "foo") != make_node_id("/repo", "a.py", "bar")


def test_make_node_id_differs_by_repo_root():
    assert make_node_id("/repo1", "a.py", "foo") != make_node_id(
        "/repo2", "a.py", "foo"
    )


def test_make_node_id_no_collision_on_concat():
    # "a\x00b\x00c" must not equal "a\x00bc\x00" — null-byte separator prevents
    # naive concatenation collisions.
    assert make_node_id("a", "b", "c") != make_node_id("a", "bc", "")


def test_node_defaults():
    node = Node(id="x", type=NodeType.FUNCTION, name="fn", file_path="f.py")
    assert node.start_line is None
    assert node.end_line is None
    assert node.language is None
    assert node.metadata == {}


def test_node_metadata_not_shared():
    a = Node(id="a", type=NodeType.FUNCTION, name="a", file_path="f.py")
    b = Node(id="b", type=NodeType.FUNCTION, name="b", file_path="f.py")
    a.metadata["key"] = "val"
    assert "key" not in b.metadata


def test_edge_defaults():
    edge = Edge(source_id="a", target_id="b", type=EdgeType.CALLS)
    assert edge.metadata == {}


def test_edge_metadata_not_shared():
    e1 = Edge(source_id="a", target_id="b", type=EdgeType.CALLS)
    e2 = Edge(source_id="c", target_id="d", type=EdgeType.CALLS)
    e1.metadata["x"] = 1
    assert "x" not in e2.metadata
