from __future__ import annotations

from codenexus.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id


async def test_get_graph_returns_nodes_and_edges(async_client):
    response = await async_client.get("/api/graph")
    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] == 2
    assert body["edge_count"] == 1
    assert len(body["nodes"]) == 2
    assert len(body["edges"]) == 1


async def test_get_graph_node_detail_found(async_client, test_store):
    node = test_store.get_all_nodes()[0]
    response = await async_client.get(f"/api/graph/node/{node.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["node"]["id"] == node.id
    assert "incoming" in body
    assert "outgoing" in body


async def test_get_graph_node_detail_not_found(async_client):
    response = await async_client.get("/api/graph/node/nonexistent-id")
    assert response.status_code == 404


async def test_blast_radius_returns_upstream_and_downstream(async_client, test_store):
    # file_node -CONTAINS-> fn_node
    # blast radius from fn_node: upstream = [file_node], downstream = []
    nodes = {n.name: n for n in test_store.get_all_nodes()}
    fn_node = nodes["my_func"]

    response = await async_client.get(f"/api/graph/blast-radius/{fn_node.id}?depth=3")
    assert response.status_code == 200
    body = response.json()
    assert body["node_id"] == fn_node.id
    assert any(n["name"] == "foo.py" for n in body["upstream"])
    assert body["downstream"] == []


async def test_blast_radius_unknown_node(async_client):
    response = await async_client.get("/api/graph/blast-radius/does-not-exist")
    assert response.status_code == 404


async def test_blast_radius_depth_param(async_client, test_store, tmp_path):
    # Add a two-hop chain: A -CALLS-> B -CALLS-> C
    a = Node(
        id=make_node_id(str(tmp_path), "chain.py", "A"),
        type=NodeType.FUNCTION,
        name="A",
        file_path="chain.py",
    )
    b = Node(
        id=make_node_id(str(tmp_path), "chain.py", "B"),
        type=NodeType.FUNCTION,
        name="B",
        file_path="chain.py",
    )
    c = Node(
        id=make_node_id(str(tmp_path), "chain.py", "C"),
        type=NodeType.FUNCTION,
        name="C",
        file_path="chain.py",
    )
    for n in (a, b, c):
        test_store.add_node(n)
    test_store.add_edge(Edge(source_id=a.id, target_id=b.id, type=EdgeType.CALLS))
    test_store.add_edge(Edge(source_id=b.id, target_id=c.id, type=EdgeType.CALLS))

    r1 = await async_client.get(f"/api/graph/blast-radius/{a.id}?depth=1")
    r3 = await async_client.get(f"/api/graph/blast-radius/{a.id}?depth=3")
    assert len(r1.json()["downstream"]) == 1  # only B
    assert len(r3.json()["downstream"]) == 2  # B and C
