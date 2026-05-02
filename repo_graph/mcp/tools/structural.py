from pathlib import Path
from typing import Any

from repo_graph.graph.queries import get_downstream_deps, get_upstream_callers
from repo_graph.graph.schema import NodeType
from repo_graph.graph.store import GraphStore


def search_nodes(
    store: GraphStore,
    query: str,
    node_type: str | None = None,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Search for nodes by name or file path."""
    type_enum = NodeType(node_type) if node_type else None
    nodes = store.search_nodes(query, node_type=type_enum, language=language)
    return [
        {
            "id": n.id,
            "name": n.name,
            "type": n.type.value,
            "file_path": n.file_path,
            "start_line": n.start_line,
            "end_line": n.end_line,
            "language": n.language,
        }
        for n in nodes
    ]


def get_node_signature(
    store: GraphStore, repo_root: str, node_id: str, snippet_lines: int = 10
) -> dict[str, Any] | None:
    """Return node metadata and a code snippet."""
    node = store.get_node(node_id)
    if not node:
        return None

    abs_path = Path(repo_root) / node.file_path
    snippet = ""
    if abs_path.exists():
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                start = max(0, node.start_line - 1)
                end = min(len(lines), node.start_line - 1 + snippet_lines)
                snippet = "".join(lines[start:end])
        except Exception as e:
            snippet = f"<Error reading file: {e}>"

    return {
        "id": node.id,
        "name": node.name,
        "type": node.type.value,
        "file_path": node.file_path,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "language": node.language,
        "metadata": node.metadata,
        "signature_snippet": snippet,
    }


def get_downstream_dependencies(
    store: GraphStore, node_id: str, depth: int = 3
) -> list[dict[str, Any]]:
    """Return nodes that depend on the given node."""
    nodes = get_downstream_deps(store, node_id, max_depth=depth)
    return [_node_to_dict(n) for n in nodes]


def get_upstream_callers(
    store: GraphStore, node_id: str, depth: int = 3
) -> list[dict[str, Any]]:
    """Return nodes that call or import the given node."""
    nodes = get_upstream_callers(store, node_id, max_depth=depth)
    return [_node_to_dict(n) for n in nodes]


def _node_to_dict(node: Any) -> dict[str, Any]:
    return {
        "id": node.id,
        "name": node.name,
        "type": node.type.value,
        "file_path": node.file_path,
        "language": node.language,
    }
