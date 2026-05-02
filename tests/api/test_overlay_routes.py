from __future__ import annotations


async def test_complexity_overlay_returns_scores(async_client, test_store):
    response = await async_client.get("/api/overlays/complexity")
    assert response.status_code == 200
    body = response.json()
    nodes = {n.name: n for n in test_store.get_all_nodes()}
    assert body[nodes["foo.py"].id] == 5
    assert body[nodes["my_func"].id] == 2


async def test_complexity_overlay_null_when_missing(async_client, test_store):
    # my_func has complexity but no churn; churn defaults to 0 not null
    # verify that a node with no complexity key gets None
    node_without = next(
        n for n in test_store.get_all_nodes() if "cyclomatic_complexity" not in n.metadata
    ) if any("cyclomatic_complexity" not in n.metadata for n in test_store.get_all_nodes()) else None

    response = await async_client.get("/api/overlays/complexity")
    body = response.json()
    if node_without is not None:
        assert body[node_without.id] is None


async def test_churn_overlay_returns_scores(async_client, test_store):
    response = await async_client.get("/api/overlays/churn")
    assert response.status_code == 200
    body = response.json()
    nodes = {n.name: n for n in test_store.get_all_nodes()}
    assert body[nodes["foo.py"].id] == 3
    assert body[nodes["my_func"].id] == 1


async def test_ownership_overlay_placeholder(async_client, test_store):
    response = await async_client.get("/api/overlays/ownership")
    assert response.status_code == 200
    body = response.json()
    for value in body.values():
        assert isinstance(value, str)
