from pathlib import Path
from typing import Any

from codenexus.graph.queries import (
    get_downstream_deps,
)
from codenexus.graph.queries import (
    get_upstream_callers as _query_upstream_callers,
)
from codenexus.graph.schema import NodeType
from codenexus.graph.store import GraphStore


def search_nodes(
    store: GraphStore,
    query: str,
    node_type: str | None = None,
    language: str | None = None,
    file_path: str | None = None,
) -> list[dict[str, Any]]:
    """Search for nodes by name or file path substring.

    Optionally filter by node_type, language, or file_path substring.
    """
    type_enum = NodeType(node_type) if node_type else None
    nodes = store.search_nodes(query, node_type=type_enum, language=language)
    if file_path is not None:
        fp_lower = file_path.lower()
        nodes = [n for n in nodes if fp_lower in n.file_path.lower()]
    return [_node_to_dict(n, include_lines=True) for n in nodes]


def get_file_symbols(store: GraphStore, file_path: str) -> list[dict[str, Any]]:
    """Return all non-file symbols defined in the given file path, sorted by start_line."""
    nodes = store.get_nodes_by_file(file_path)
    symbols = [n for n in nodes if n.type != NodeType.FILE]
    symbols.sort(key=lambda n: n.start_line or 0)
    return [_node_to_dict(n, include_lines=True) for n in symbols]


def get_node_signature(
    store: GraphStore, repo_root: str, node_id: str, snippet_lines: int = 10
) -> dict[str, Any] | None:
    """Return node metadata and a code snippet. Uses the full node body when end_line is known."""
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
                if node.end_line is not None:
                    end = min(len(lines), node.end_line)
                else:
                    end = min(len(lines), node.start_line - 1 + snippet_lines)
                snippet = "".join(lines[start:end])
        except Exception as e:
            snippet = f"<Error reading file: {e}>"

    return {
        **_node_to_dict(node, include_lines=True),
        "metadata": node.metadata,
        "signature_snippet": snippet,
    }


def search_field_usages(
    store: GraphStore,
    field_name: str,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Find all nodes that access the given field/property name, with line numbers."""
    nodes = store.search_nodes_with_field_access(field_name, language=language)
    results = []
    for node in nodes:
        d = _node_to_dict(node, include_lines=True)
        d["usages_at_lines"] = node.metadata["accessed_fields"][field_name]
        results.append(d)
    return results


def get_downstream_dependencies(
    store: GraphStore, node_id: str, depth: int = 3
) -> list[dict[str, Any]]:
    """Return nodes that this node calls or imports (i.e. its outgoing dependencies)."""
    nodes = get_downstream_deps(store, node_id, max_depth=depth)
    return [_node_to_dict(n, include_lines=True) for n in nodes]


def get_upstream_callers(store: GraphStore, node_id: str, depth: int = 3) -> list[dict[str, Any]]:
    """Return nodes that call or import the given node (i.e. its callers/consumers)."""
    nodes = _query_upstream_callers(store, node_id, max_depth=depth)
    return [_node_to_dict(n, include_lines=True) for n in nodes]


def _node_to_dict(node: Any, include_lines: bool = False) -> dict[str, Any]:
    if node.type == NodeType.FILE:
        qualified_name = node.file_path
    else:
        qualified_name = f"{node.file_path}::{node.name}"
    d: dict[str, Any] = {
        "id": node.id,
        "qualified_name": qualified_name,
        "name": node.name,
        "type": node.type.value,
        "file_path": node.file_path,
        "language": node.language,
    }
    if include_lines:
        d["start_line"] = node.start_line
        d["end_line"] = node.end_line
    return d
