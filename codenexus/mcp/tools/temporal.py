"""Temporal MCP tools: node history and graph-at-commit reconstruction."""

from __future__ import annotations

from typing import Any

from codenexus.graph.store import GraphStore
from codenexus.ingestion.diff_snapshot import (
    get_graph_at_commit,
    get_node_history,
    list_commits,
)


def get_node_history_tool(store: GraphStore, node_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return commits that touched *node_id*, newest first."""
    return get_node_history(store, node_id, limit=limit)


def get_graph_at_commit_tool(store: GraphStore, commit_sha: str) -> dict[str, Any]:
    """Return the full graph state as it existed after *commit_sha*."""
    rows = store._db.execute(
        "SELECT 1 FROM commit_snapshots WHERE commit_sha = ?", (commit_sha,)
    ).fetchall()
    if not rows:
        return {"error": f"Commit {commit_sha!r} not found"}
    return get_graph_at_commit(store, commit_sha)


def list_commits_tool(store: GraphStore, limit: int = 500) -> list[dict[str, Any]]:
    """Return all commits with stored snapshots, newest first."""
    return list_commits(store, limit=limit)
