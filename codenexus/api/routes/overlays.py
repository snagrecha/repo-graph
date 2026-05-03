from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from codenexus.api.dependencies import get_store
from codenexus.graph.store import GraphStore

router = APIRouter(prefix="/api/overlays", tags=["overlays"])


def _collect_overlay(store: GraphStore, key: str, default) -> dict:
    return {node.id: node.metadata.get(key, default) for node in store.get_all_nodes()}


@router.get("/complexity")
async def get_complexity_overlay(
    store: GraphStore = Depends(get_store),
) -> dict[str, float | None]:
    return await asyncio.to_thread(_collect_overlay, store, "cyclomatic_complexity", None)


@router.get("/churn")
async def get_churn_overlay(
    store: GraphStore = Depends(get_store),
) -> dict[str, int]:
    return await asyncio.to_thread(_collect_overlay, store, "churn_score", 0)


@router.get("/ownership")
async def get_ownership_overlay(
    store: GraphStore = Depends(get_store),
) -> dict[str, str]:
    # Phase 2: full git blame per node. Placeholder returns metadata field if present.
    return await asyncio.to_thread(_collect_overlay, store, "primary_owner", "unknown")
