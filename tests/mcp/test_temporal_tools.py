import msgpack

from codenexus.mcp.tools import temporal

_INSERT_SNAPSHOT = (
    "INSERT INTO commit_snapshots (commit_sha, committed_at, author, message, diff_patch) "
    "VALUES (?, ?, ?, ?, ?)"
)


def test_get_node_history_tool_returns_commits(tmp_store):
    store = tmp_store
    store._db.execute(
        _INSERT_SNAPSHOT,
        ("sha1", 1000, "alice", "fix", b"\x81\xa4test\xa3val"),
    )
    store._db.execute(
        "INSERT INTO node_commits (node_id, commit_sha) VALUES (?, ?)",
        ("n1", "sha1"),
    )
    store._db.commit()

    result = temporal.get_node_history_tool(store, "n1", limit=10)
    assert len(result) == 1
    assert result[0]["commit_sha"] == "sha1"
    assert result[0]["author"] == "alice"


def test_get_node_history_tool_empty_for_unknown_node(tmp_store):
    store = tmp_store
    result = temporal.get_node_history_tool(store, "nope", limit=10)
    assert result == []


def test_get_graph_at_commit_tool_reconstructs(tmp_store):
    store = tmp_store
    patch = {
        "nodes_added": [
            {
                "id": "n1",
                "type": "function",
                "name": "foo",
                "file_path": "a.py",
                "start_line": 1,
                "end_line": 2,
                "language": "python",
                "metadata": {},
            }
        ],
        "nodes_removed": [],
        "nodes_unchanged": [],
        "edges_added": [],
        "edges_removed": [],
    }
    store._db.execute(
        _INSERT_SNAPSHOT,
        ("sha1", 1000, "a", "m", msgpack.packb(patch)),
    )
    store._db.commit()

    result = temporal.get_graph_at_commit_tool(store, "sha1")
    assert result["node_count"] == 1
    assert result["nodes"][0]["id"] == "n1"


def test_list_commits_tool(tmp_store):
    store = tmp_store
    for i, sha in enumerate(["a", "b"]):
        store._db.execute(
            _INSERT_SNAPSHOT,
            (sha, (i + 1) * 1000, "dev", f"c {sha}", b"\x81\xa4test\xa3val"),
        )
    store._db.commit()

    result = temporal.list_commits_tool(store, limit=10)
    assert len(result) == 2
    assert result[0]["commit_sha"] == "b"  # newest first
