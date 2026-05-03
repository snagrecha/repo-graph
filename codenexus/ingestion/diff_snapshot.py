"""Generate per-commit graph diff snapshots for time-travel support.

Each commit is analysed by parsing the source code of every modified file
both *before* and *after* the commit, computing the delta of nodes and
edges, and storing a compact msgpack blob in SQLite.

Timeline scrubbing later replays these diffs sequentially to reconstruct the
graph at any historical commit without re-parsing the repository from scratch.
"""

from __future__ import annotations

import logging
from pathlib import Path

import msgpack
from pydriller import Repository

from codenexus.graph.schema import Edge, EdgeType, Node, NodeType
from codenexus.graph.store import GraphStore
from codenexus.ingestion.parser import _MAX_FILE_BYTES, LANGUAGE_PARSERS

logger = logging.getLogger(__name__)

_SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS commit_snapshots (
    commit_sha   TEXT PRIMARY KEY,
    committed_at INTEGER NOT NULL,
    author       TEXT NOT NULL,
    message      TEXT NOT NULL,
    diff_patch   BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS node_commits (
    node_id      TEXT NOT NULL,
    commit_sha   TEXT NOT NULL,
    PRIMARY KEY (node_id, commit_sha)
);
"""


def _node_to_dict(node: Node) -> dict:
    return {
        "id": node.id,
        "type": node.type.value,
        "name": node.name,
        "file_path": node.file_path,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "language": node.language,
        "metadata": node.metadata,
    }


def _edge_to_dict(edge: Edge) -> dict:
    return {
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "type": edge.type.value,
        "metadata": edge.metadata,
    }


def _dict_to_node(d: dict) -> Node:
    return Node(
        id=d["id"],
        type=NodeType(d["type"]),
        name=d["name"],
        file_path=d["file_path"],
        start_line=d.get("start_line"),
        end_line=d.get("end_line"),
        language=d.get("language"),
        metadata=d.get("metadata", {}),
    )


def _dict_to_edge(d: dict) -> Edge:
    return Edge(
        source_id=d["source_id"],
        target_id=d["target_id"],
        type=EdgeType(d["type"]),
        metadata=d.get("metadata", {}),
    )


def _parse_source_bytes(
    source: bytes | None, file_path: str, repo_root: str
) -> tuple[list[Node], list[Edge]] | None:
    """Parse raw source bytes into nodes and edges."""
    if source is None:
        return None

    ext = Path(file_path).suffix.lower()
    entry = LANGUAGE_PARSERS.get(ext)
    if entry is None:
        return None

    if len(source) > _MAX_FILE_BYTES:
        return None

    ts_parser, extractor = entry
    try:
        tree = ts_parser.parse(source)
        return extractor.extract_nodes_and_edges(tree, file_path, repo_root)
    except Exception as exc:
        logger.warning("Failed to parse %s for diff snapshot: %s", file_path, exc)
        return None


def _compute_file_diff(
    old_nodes: list[Node],
    old_edges: list[Edge],
    new_nodes: list[Node],
    new_edges: list[Edge],
) -> dict:
    """Return the delta between two graph states for a single file."""
    old_node_ids = {n.id for n in old_nodes}
    new_node_ids = {n.id for n in new_nodes}

    old_edge_keys = {(e.source_id, e.target_id, e.type.value) for e in old_edges}
    new_edge_keys = {(e.source_id, e.target_id, e.type.value) for e in new_edges}

    nodes_added = [n for n in new_nodes if n.id not in old_node_ids]
    nodes_removed = [n for n in old_nodes if n.id not in new_node_ids]
    # Nodes that survived unchanged in this commit — used for node_commits
    nodes_unchanged = [n for n in new_nodes if n.id in old_node_ids]

    edges_added = [
        e for e in new_edges if (e.source_id, e.target_id, e.type.value) not in old_edge_keys
    ]
    edges_removed = [
        e for e in old_edges if (e.source_id, e.target_id, e.type.value) not in new_edge_keys
    ]

    return {
        "nodes_added": [_node_to_dict(n) for n in nodes_added],
        "nodes_removed": [n.id for n in nodes_removed],
        "nodes_unchanged": [n.id for n in nodes_unchanged],
        "edges_added": [_edge_to_dict(e) for e in edges_added],
        "edges_removed": [
            {"source_id": e.source_id, "target_id": e.target_id, "type": e.type.value}
            for e in edges_removed
        ],
    }


def generate_diff_snapshots(repo_root: str, store: GraphStore) -> None:
    """Walk git history and generate diff snapshots for every commit.

    This is intentionally run only during a *full re-index* because it
    re-parses every modified file at every commit, which is CPU-intensive.
    """
    logger.info("Starting diff snapshot generation for %s", repo_root)

    store._db.executescript(_SNAPSHOT_SCHEMA)
    store._db.commit()

    repo_path = Path(repo_root).resolve()

    # Already-processed commits so that ``sync`` can resume incrementally.
    processed: set[str] = {
        row["commit_sha"]
        for row in store._db.execute("SELECT commit_sha FROM commit_snapshots").fetchall()
    }

    total_new = 0
    total_skipped = 0

    try:
        for commit in Repository(str(repo_path)).traverse_commits():
            sha = commit.hash
            if sha in processed:
                total_skipped += 1
                continue

            commit_diff: dict = {
                "commit_sha": sha,
                "files_changed": [],
                "nodes_added": [],
                "nodes_removed": [],
                "nodes_unchanged": [],
                "edges_added": [],
                "edges_removed": [],
            }

            for mod in commit.modified_files:
                old_path = mod.old_path
                new_path = mod.new_path

                if not old_path and not new_path:
                    continue

                # Determine absolute paths for old and new file states
                old_abs = str((repo_path / old_path).resolve()) if old_path else None
                new_abs = str((repo_path / new_path).resolve()) if new_path else None

                # Encode PyDriller strings -> bytes for tree-sitter
                old_source = (
                    mod.source_code_before.encode("utf-8", errors="replace")
                    if mod.source_code_before is not None
                    else None
                )
                new_source = (
                    mod.source_code.encode("utf-8", errors="replace")
                    if mod.source_code is not None
                    else None
                )

                old_result = (
                    _parse_source_bytes(old_source, old_abs, repo_root) if old_abs else None
                )
                new_result = (
                    _parse_source_bytes(new_source, new_abs, repo_root) if new_abs else None
                )

                change_type = _classify_change(old_path, new_path, old_source, new_source)
                commit_diff["files_changed"].append(
                    {
                        "old_path": old_path,
                        "new_path": new_path,
                        "change_type": change_type,
                    }
                )

                old_nodes = old_result[0] if old_result else []
                old_edges = old_result[1] if old_result else []
                new_nodes = new_result[0] if new_result else []
                new_edges = new_result[1] if new_result else []

                file_diff = _compute_file_diff(old_nodes, old_edges, new_nodes, new_edges)

                commit_diff["nodes_added"].extend(file_diff["nodes_added"])
                commit_diff["nodes_removed"].extend(file_diff["nodes_removed"])
                commit_diff["nodes_unchanged"].extend(file_diff["nodes_unchanged"])
                commit_diff["edges_added"].extend(file_diff["edges_added"])
                commit_diff["edges_removed"].extend(file_diff["edges_removed"])

                # Record node→commit associations for history lookups
                touched_ids = (
                    set(file_diff["nodes_removed"])
                    | {n["id"] for n in file_diff["nodes_added"]}
                    | set(file_diff["nodes_unchanged"])
                )
                for nid in touched_ids:
                    store._db.execute(
                        "INSERT OR IGNORE INTO node_commits (node_id, commit_sha) VALUES (?, ?)",
                        (nid, sha),
                    )

            # Persist the commit diff patch
            patch_blob = msgpack.packb(commit_diff)
            store._db.execute(
                """
                INSERT INTO commit_snapshots (commit_sha, committed_at, author, message, diff_patch)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(commit_sha) DO NOTHING
                """,
                (
                    sha,
                    int(commit.committer_date.timestamp()),
                    commit.author.name or "unknown",
                    commit.msg or "",
                    patch_blob,
                ),
            )

            total_new += 1
            if total_new % 100 == 0:
                store._db.commit()
                logger.info("Processed %d new commits...", total_new)

        store._db.commit()
        logger.info(
            "Diff snapshot generation complete: %d new commits, %d skipped.",
            total_new,
            total_skipped,
        )

    except Exception as exc:
        store._db.commit()
        logger.error("Diff snapshot generation failed: %s", exc)
        raise


def _classify_change(
    old_path: str | None,
    new_path: str | None,
    old_source: bytes | None,
    new_source: bytes | None,
) -> str:
    """Classify a file modification for metadata."""
    if old_path is None:
        return "add"
    if new_path is None:
        return "delete"
    if old_path != new_path:
        return "rename"
    return "modify"


# ------------------------------------------------------------------
# Replay helpers (used by temporal tools and timeline routes)
# ------------------------------------------------------------------


def _replay_diffs(
    store: GraphStore, up_to_commit: str | None = None
) -> tuple[dict[str, Node], dict[tuple[str, str, str], Edge]]:
    """Replay stored diff patches in chronological order.

    Returns the reconstructed graph state as two dicts:
      - nodes:   id -> Node
      - edges:   (source_id, target_id, type) -> Edge

    If *up_to_commit* is provided, replay stops after that commit is applied.
    """
    nodes: dict[str, Node] = {}
    edges: dict[tuple[str, str, str], Edge] = {}

    rows = store._db.execute(
        "SELECT commit_sha, diff_patch FROM commit_snapshots ORDER BY committed_at ASC"
    ).fetchall()

    for row in rows:
        diff = msgpack.unpackb(row["diff_patch"], raw=False)

        # Remove nodes first (edges may reference them)
        for nid in diff.get("nodes_removed", []):
            nodes.pop(nid, None)

        # Add / update nodes
        for nd in diff.get("nodes_added", []):
            node = _dict_to_node(nd)
            nodes[node.id] = node

        # Remove edges
        for ed in diff.get("edges_removed", []):
            key = (ed["source_id"], ed["target_id"], ed["type"])
            edges.pop(key, None)

        # Add edges
        for ed in diff.get("edges_added", []):
            edge = _dict_to_edge(ed)
            key = (edge.source_id, edge.target_id, edge.type.value)
            edges[key] = edge

        if up_to_commit and row["commit_sha"] == up_to_commit:
            break

    return nodes, edges


def get_graph_at_commit(store: GraphStore, commit_sha: str) -> dict:
    """Return the full graph (nodes + edges) as it existed after *commit_sha*."""
    nodes, edges = _replay_diffs(store, up_to_commit=commit_sha)
    return {
        "nodes": [_node_to_dict(n) for n in nodes.values()],
        "edges": [_edge_to_dict(e) for e in edges.values()],
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def get_node_history(store: GraphStore, node_id: str, limit: int = 10) -> list[dict]:
    """Return commits that touched *node_id*, newest first."""
    rows = store._db.execute(
        """
        SELECT cs.commit_sha, cs.committed_at, cs.author, cs.message
        FROM commit_snapshots cs
        JOIN node_commits nc ON cs.commit_sha = nc.commit_sha
        WHERE nc.node_id = ?
        ORDER BY cs.committed_at DESC
        LIMIT ?
        """,
        (node_id, limit),
    ).fetchall()

    return [
        {
            "commit_sha": row["commit_sha"],
            "committed_at": row["committed_at"],
            "author": row["author"],
            "message": row["message"],
        }
        for row in rows
    ]


def list_commits(store: GraphStore, limit: int = 500) -> list[dict]:
    """Return all commits with snapshots, newest first."""
    rows = store._db.execute(
        """
        SELECT commit_sha, committed_at, author, message
        FROM commit_snapshots
        ORDER BY committed_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return [
        {
            "commit_sha": row["commit_sha"],
            "committed_at": row["committed_at"],
            "author": row["author"],
            "message": row["message"],
        }
        for row in rows
    ]
