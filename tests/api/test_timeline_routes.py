import msgpack
import pytest

INSERT_SNAPSHOT = (
    "INSERT INTO commit_snapshots (commit_sha, committed_at, author, message, diff_patch) "
    "VALUES (?, ?, ?, ?, ?)"
)


@pytest.mark.asyncio
async def test_get_commits_returns_list(async_client, test_store):
    test_store._db.execute(
        INSERT_SNAPSHOT,
        ("abc", 1000, "dev", "init", b"\x81\xa4test\xa3val"),
    )
    test_store._db.commit()

    response = await async_client.get("/api/timeline/commits")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["commit_sha"] == "abc"


@pytest.mark.asyncio
async def test_get_commit_graph_reconstructs(async_client, test_store):
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
    test_store._db.execute(
        INSERT_SNAPSHOT,
        ("sha1", 1000, "a", "m", msgpack.packb(patch)),
    )
    test_store._db.commit()

    response = await async_client.get("/api/timeline/commits/sha1")
    assert response.status_code == 200
    data = response.json()
    assert data["node_count"] == 1
    assert data["nodes"][0]["id"] == "n1"


@pytest.mark.asyncio
async def test_get_commit_graph_404_for_unknown(async_client):
    response = await async_client.get("/api/timeline/commits/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_node_history(async_client, test_store):
    test_store._db.execute(
        INSERT_SNAPSHOT,
        ("sha1", 1000, "dev", "fix", b"\x81\xa4test\xa3val"),
    )
    test_store._db.execute(
        "INSERT INTO node_commits (node_id, commit_sha) VALUES (?, ?)",
        ("n1", "sha1"),
    )
    test_store._db.commit()

    response = await async_client.get("/api/timeline/node/n1/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["commit_sha"] == "sha1"
