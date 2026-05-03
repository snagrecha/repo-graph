"""REST API routes for git timeline and historical graph reconstruction."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from codenexus.api.dependencies import get_store
from codenexus.api.serializers import (
    EdgeResponse,
    GraphResponse,
    NodeResponse,
)
from codenexus.graph.store import GraphStore
from codenexus.ingestion.diff_snapshot import (
    get_graph_at_commit,
    get_node_history,
    list_commits,
)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.get("/commits")
async def get_commits(
    limit: int = Query(default=500, ge=1, le=5000),
    store: GraphStore = Depends(get_store),
) -> list[dict[str, Any]]:
    def _fetch():
        return list_commits(store, limit=limit)

    return await asyncio.to_thread(_fetch)


@router.get("/commits/{commit_sha}")
async def get_commit_graph(
    commit_sha: str,
    store: GraphStore = Depends(get_store),
) -> GraphResponse:
    def _fetch():
        return get_graph_at_commit(store, commit_sha)

    data = await asyncio.to_thread(_fetch)
    if not data.get("nodes") and not data.get("edges"):
        # It could legitimately be empty, but check if the commit exists
        rows = store._db.execute(
            "SELECT 1 FROM commit_snapshots WHERE commit_sha = ?", (commit_sha,)
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"Commit {commit_sha!r} not found")

    return GraphResponse(
        nodes=[NodeResponse(**n) for n in data["nodes"]],
        edges=[EdgeResponse(**e) for e in data["edges"]],
        node_count=data["node_count"],
        edge_count=data["edge_count"],
    )


@router.get("/node/{node_id}/history")
async def get_node_commit_history(
    node_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    store: GraphStore = Depends(get_store),
) -> list[dict[str, Any]]:
    def _fetch():
        return get_node_history(store, node_id, limit=limit)

    return await asyncio.to_thread(_fetch)
