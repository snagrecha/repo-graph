import pytest

from codenexus.graph.store import GraphStore


@pytest.fixture
def tmp_store(tmp_path):
    with GraphStore(tmp_path / "graph.db") as store:
        yield store
