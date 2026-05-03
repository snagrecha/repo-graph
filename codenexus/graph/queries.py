from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from codenexus.graph.schema import EdgeType, Node

if TYPE_CHECKING:
    from codenexus.graph.store import GraphStore


def get_downstream_deps(
    store: GraphStore,
    node_id: str,
    max_depth: int = 3,
    edge_types: set[EdgeType] | None = None,
) -> list[Node]:
    """BFS over outgoing edges; returns nodes reachable within max_depth hops."""
    return _bfs(store, node_id, max_depth, edge_types, outgoing=True)


def get_upstream_callers(
    store: GraphStore,
    node_id: str,
    max_depth: int = 3,
    edge_types: set[EdgeType] | None = None,
) -> list[Node]:
    """BFS over incoming edges; returns nodes that transitively reach node_id."""
    return _bfs(store, node_id, max_depth, edge_types, outgoing=False)


def _bfs(
    store: GraphStore,
    start_id: str,
    max_depth: int,
    edge_types: set[EdgeType] | None,
    outgoing: bool,
) -> list[Node]:
    visited: set[str] = {start_id}
    queue: deque[tuple[str, int]] = deque([(start_id, 0)])
    result: list[Node] = []

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        if outgoing:
            edges = store.get_outgoing_edges(current_id)
            neighbor_ids = [
                e.target_id for e in edges if edge_types is None or e.type in edge_types
            ]
        else:
            edges = store.get_incoming_edges(current_id)
            neighbor_ids = [
                e.source_id for e in edges if edge_types is None or e.type in edge_types
            ]

        for nid in neighbor_ids:
            if nid not in visited:
                visited.add(nid)
                node = store.get_node(nid)
                if node is not None:
                    result.append(node)
                    queue.append((nid, depth + 1))

    return result
