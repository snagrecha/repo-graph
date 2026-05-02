from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from repo_graph.api.dependencies import get_repo_root, get_store
from repo_graph.api.serializers import (
    BlastRadiusResponse,
    GraphResponse,
    NodeDetailResponse,
    serialize_edge,
    serialize_node,
)
from repo_graph.graph.queries import get_downstream_deps, get_upstream_callers
from repo_graph.graph.store import GraphStore

router = APIRouter(prefix="/api/graph", tags=["graph"])


def _collect_graph(store: GraphStore) -> tuple:
    nodes = store.get_all_nodes()
    edges = []
    for node in nodes:
        edges.extend(store.get_outgoing_edges(node.id))
    return nodes, edges


@router.get("", response_model=GraphResponse)
async def get_graph(store: GraphStore = Depends(get_store)) -> GraphResponse:
    nodes, edges = await asyncio.to_thread(_collect_graph, store)
    return GraphResponse(
        nodes=[serialize_node(n) for n in nodes],
        edges=[serialize_edge(e) for e in edges],
        node_count=len(nodes),
        edge_count=len(edges),
    )


@router.get("/node/{node_id}", response_model=NodeDetailResponse)
async def get_node_detail(
    node_id: str,
    store: GraphStore = Depends(get_store),
) -> NodeDetailResponse:
    def _fetch(store: GraphStore):
        node = store.get_node(node_id)
        if node is None:
            return None, [], []
        return (
            node,
            store.get_incoming_edges(node_id),
            store.get_outgoing_edges(node_id),
        )

    node, incoming, outgoing = await asyncio.to_thread(_fetch, store)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")

    return NodeDetailResponse(
        node=serialize_node(node),
        incoming=[serialize_edge(e) for e in incoming],
        outgoing=[serialize_edge(e) for e in outgoing],
    )


@router.get("/blast-radius/{node_id}", response_model=BlastRadiusResponse)
async def get_blast_radius(
    node_id: str,
    depth: int = Query(default=3, ge=1, le=10),
    store: GraphStore = Depends(get_store),
) -> BlastRadiusResponse:
    def _fetch(store: GraphStore):
        if store.get_node(node_id) is None:
            return None, None
        upstream = get_upstream_callers(store, node_id, max_depth=depth)
        downstream = get_downstream_deps(store, node_id, max_depth=depth)
        return upstream, downstream

    upstream, downstream = await asyncio.to_thread(_fetch, store)
    if upstream is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id!r} not found")

    return BlastRadiusResponse(
        node_id=node_id,
        upstream=[serialize_node(n) for n in upstream],
        downstream=[serialize_node(n) for n in downstream],
    )
