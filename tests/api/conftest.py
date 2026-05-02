from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from repo_graph.api import dependencies
from repo_graph.api.app import create_app
from repo_graph.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id
from repo_graph.graph.store import GraphStore


@pytest.fixture()
def test_store(tmp_path):
    db_path = tmp_path / "graph.db"
    store = GraphStore(db_path)

    file_node = Node(
        id=make_node_id(str(tmp_path), "src/foo.py", "src/foo.py"),
        type=NodeType.FILE,
        name="foo.py",
        file_path="src/foo.py",
        language="python",
        metadata={"cyclomatic_complexity": 5, "churn_score": 3, "primary_owner": "alice"},
    )
    fn_node = Node(
        id=make_node_id(str(tmp_path), "src/foo.py", "my_func"),
        type=NodeType.FUNCTION,
        name="my_func",
        file_path="src/foo.py",
        start_line=10,
        end_line=20,
        language="python",
        metadata={"cyclomatic_complexity": 2, "churn_score": 1},
    )
    store.add_node(file_node)
    store.add_node(fn_node)
    store.add_edge(
        Edge(
            source_id=file_node.id,
            target_id=fn_node.id,
            type=EdgeType.CONTAINS,
        )
    )

    yield store
    store.close()


@pytest.fixture()
def test_app(test_store, tmp_path):
    # Reset module-level singletons between tests
    dependencies._store = None
    dependencies._repo_root = ""
    return create_app(test_store, str(tmp_path))


@pytest_asyncio.fixture()
async def async_client(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client
