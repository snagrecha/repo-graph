from codenexus.graph.schema import Edge, EdgeType, Node, NodeType
from codenexus.ingestion.diff_snapshot import (
    _compute_file_diff,
    _dict_to_edge,
    _dict_to_node,
    _edge_to_dict,
    _node_to_dict,
    get_graph_at_commit,
    get_node_history,
    list_commits,
)


def _make_node(node_id, name, file_path, node_type=NodeType.FUNCTION):
    return Node(
        id=node_id,
        type=node_type,
        name=name,
        file_path=file_path,
        start_line=1,
        end_line=10,
        language="python",
        metadata={},
    )


def test_node_roundtrip():
    node = _make_node("n1", "foo", "src/a.py")
    d = _node_to_dict(node)
    restored = _dict_to_node(d)
    assert restored.id == node.id
    assert restored.type == node.type
    assert restored.name == node.name
    assert restored.file_path == node.file_path


def test_edge_roundtrip():
    edge = Edge(source_id="s1", target_id="t1", type=EdgeType.CALLS, metadata={"x": 1})
    d = _edge_to_dict(edge)
    restored = _dict_to_edge(d)
    assert restored.source_id == edge.source_id
    assert restored.target_id == edge.target_id
    assert restored.type == edge.type
    assert restored.metadata == edge.metadata


def test_compute_file_diff_adds_and_removes():
    old_nodes = [_make_node("n1", "old_fn", "src/a.py")]
    old_edges = [Edge(source_id="n1", target_id="n2", type=EdgeType.CALLS)]
    new_nodes = [_make_node("n2", "new_fn", "src/a.py")]
    new_edges = [Edge(source_id="n2", target_id="n3", type=EdgeType.IMPORTS)]

    diff = _compute_file_diff(old_nodes, old_edges, new_nodes, new_edges)

    assert len(diff["nodes_added"]) == 1
    assert diff["nodes_added"][0]["id"] == "n2"
    assert diff["nodes_removed"] == ["n1"]
    assert diff["nodes_unchanged"] == []

    assert len(diff["edges_added"]) == 1
    assert diff["edges_added"][0]["source_id"] == "n2"
    assert len(diff["edges_removed"]) == 1
    assert diff["edges_removed"][0]["source_id"] == "n1"


def test_compute_file_diff_no_change():
    nodes = [_make_node("n1", "fn", "src/a.py")]
    edges = [Edge(source_id="n1", target_id="n2", type=EdgeType.CALLS)]
    diff = _compute_file_diff(nodes, edges, nodes, edges)

    assert diff["nodes_added"] == []
    assert diff["nodes_removed"] == []
    assert diff["nodes_unchanged"] == ["n1"]
    assert diff["edges_added"] == []
    assert diff["edges_removed"] == []


def test_get_node_history_queries_junction_table(tmp_store):
    store = tmp_store
    store._db.execute(
        """
        INSERT INTO commit_snapshots (commit_sha, committed_at, author, message, diff_patch)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("abc123", 1000, "alice", "fix bug", b"\x81\xa4test\xa3val"),
    )
    store._db.execute(
        "INSERT INTO node_commits (node_id, commit_sha) VALUES (?, ?)",
        ("n1", "abc123"),
    )
    store._db.commit()

    history = get_node_history(store, "n1", limit=10)
    assert len(history) == 1
    assert history[0]["commit_sha"] == "abc123"
    assert history[0]["author"] == "alice"
    assert history[0]["message"] == "fix bug"


def test_list_commits_returns_descending(tmp_store):
    store = tmp_store
    for i, sha in enumerate(["aaa", "bbb", "ccc"]):
        store._db.execute(
            """
            INSERT INTO commit_snapshots (commit_sha, committed_at, author, message, diff_patch)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sha, (i + 1) * 1000, "dev", f"commit {sha}", b"\x81\xa4test\xa3val"),
        )
    store._db.commit()

    commits = list_commits(store, limit=10)
    assert len(commits) == 3
    # Newest first
    assert commits[0]["commit_sha"] == "ccc"
    assert commits[1]["commit_sha"] == "bbb"
    assert commits[2]["commit_sha"] == "aaa"


def test_get_graph_at_commit_replays_diffs(tmp_store):
    store = tmp_store

    # Commit 1: add node n1
    patch1 = {
        "nodes_added": [_node_to_dict(_make_node("n1", "foo", "src/a.py"))],
        "nodes_removed": [],
        "nodes_unchanged": [],
        "edges_added": [],
        "edges_removed": [],
    }
    import msgpack

    store._db.execute(
        """
        INSERT INTO commit_snapshots (commit_sha, committed_at, author, message, diff_patch)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("c1", 1000, "a", "c1", msgpack.packb(patch1)),
    )

    # Commit 2: add node n2, remove n1
    patch2 = {
        "nodes_added": [_node_to_dict(_make_node("n2", "bar", "src/b.py"))],
        "nodes_removed": ["n1"],
        "nodes_unchanged": [],
        "edges_added": [],
        "edges_removed": [],
    }
    store._db.execute(
        """
        INSERT INTO commit_snapshots (commit_sha, committed_at, author, message, diff_patch)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("c2", 2000, "a", "c2", msgpack.packb(patch2)),
    )
    store._db.commit()

    # After c1: should have n1
    g1 = get_graph_at_commit(store, "c1")
    ids1 = {n["id"] for n in g1["nodes"]}
    assert ids1 == {"n1"}

    # After c2: should have n2 only
    g2 = get_graph_at_commit(store, "c2")
    ids2 = {n["id"] for n in g2["nodes"]}
    assert ids2 == {"n2"}
