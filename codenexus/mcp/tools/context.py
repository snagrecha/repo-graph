"""Context Pruning Engine — deterministic context narrowing for AI agents.

Given a target node and a natural-language goal, this module extracts the
1-hop ego graph, scores each neighbour by keyword overlap against the goal
(and optionally commit messages), and returns a compact JSON structure
containing only the most relevant source snippets, capped by a token budget.

No LLM calls are made inside this tool.  Scoring is fully deterministic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from codenexus.graph.queries import get_downstream_deps, get_upstream_callers
from codenexus.graph.schema import Node
from codenexus.graph.store import GraphStore

logger = __import__("logging").getLogger(__name__)

# Rough code-token heuristic: ~4 chars per token for typical source code.
_CHAR_PER_TOKEN = 4


def get_narrowed_context(
    store: GraphStore,
    repo_root: str,
    node_id: str,
    goal: str,
    max_tokens: int = 8000,
) -> dict[str, Any]:
    """Return a minimised code context for *node_id* relevant to *goal*.

    Steps:
        1. Fetch the target node.
        2. Build the 1-hop ego graph (direct callers + callees).
        3. Score every neighbour by keyword overlap with *goal*.
        4. Greedily pack the highest-scoring snippets until *max_tokens*.
        5. Always include the target node first (it is the anchor).
    """
    target = store.get_node(node_id)
    if target is None:
        return {"error": f"Node {node_id!r} not found"}

    # --- 1. 1-hop ego graph ---
    downstream = get_downstream_deps(store, node_id, max_depth=1)
    upstream = get_upstream_callers(store, node_id, max_depth=1)

    # Deduplicate neighbours while preserving order (downstream first)
    seen: set[str] = set()
    neighbours: list[Node] = []
    for n in downstream + upstream:
        if n.id != node_id and n.id not in seen:
            seen.add(n.id)
            neighbours.append(n)

    # --- 2. Score by keyword overlap ---
    goal_tokens = set(re.findall(r"\b\w+\b", goal.lower()))

    def _score(node: Node) -> float:
        text = f"{node.name} {node.file_path}".lower()
        node_tokens = set(re.findall(r"\b\w+\b", text))
        overlap = len(goal_tokens & node_tokens)
        # Also consider metadata keys for a small boost
        meta_boost = sum(0.5 for k in node.metadata if any(g in k.lower() for g in goal_tokens))
        return overlap + meta_boost

    neighbours.sort(key=_score, reverse=True)

    # --- 3. Greedy snippet packing ---
    snippets: list[dict[str, Any]] = []
    total_tokens = 0

    def _add_snippet(node: Node, relevance: float) -> bool:
        nonlocal total_tokens
        snippet = _read_snippet(node, repo_root)
        tokens = max(1, len(snippet) // _CHAR_PER_TOKEN)

        if total_tokens + tokens > max_tokens and snippets:
            # Budget exhausted (and we're not the mandatory anchor node)
            return False

        snippets.append(
            {
                "node_id": node.id,
                "qualified_name": _qualified_name(node),
                "type": node.type.value,
                "file_path": node.file_path,
                "relevance": round(relevance, 3),
                "tokens": tokens,
                "snippet": snippet,
            }
        )
        total_tokens += tokens
        return True

    # Anchor node is always included first
    _add_snippet(target, relevance=1.0)

    for nb in neighbours:
        if not _add_snippet(nb, relevance=_score(nb)):
            break

    return {
        "target_node": {
            "id": target.id,
            "qualified_name": _qualified_name(target),
            "type": target.type.value,
            "file_path": target.file_path,
        },
        "goal": goal,
        "max_tokens": max_tokens,
        "used_tokens": total_tokens,
        "snippet_count": len(snippets),
        "snippets": snippets,
    }


def _qualified_name(node: Node) -> str:
    if node.type.value == "file":
        return node.file_path
    return f"{node.file_path}::{node.name}"


def _read_snippet(node: Node, repo_root: str) -> str:
    """Read the source body bounded by the node's line range."""
    abs_path = Path(repo_root) / node.file_path
    if not abs_path.exists():
        return ""

    try:
        with open(abs_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as exc:
        logger.warning("Cannot read %s: %s", abs_path, exc)
        return ""

    if not lines:
        return ""

    start = max(0, (node.start_line or 1) - 1)
    if node.end_line is not None:
        end = min(len(lines), node.end_line)
    else:
        end = min(len(lines), start + 10)

    return "".join(lines[start:end])
