from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import rustworkx

from codenexus.graph.schema import Edge, EdgeType, Node, NodeType

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    start_line  INTEGER,
    end_line    INTEGER,
    language    TEXT,
    metadata    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    type        TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (source_id, target_id, type)
);

CREATE INDEX IF NOT EXISTS idx_nodes_file_path ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_nodes_type      ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_name      ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_edges_source    ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target    ON edges(target_id);

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id   TEXT NOT NULL,
    repo_root    TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    last_active  INTEGER NOT NULL,
    PRIMARY KEY (session_id)
);

CREATE TABLE IF NOT EXISTS agent_actions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL,
    node_id        TEXT,
    action         TEXT NOT NULL,
    timestamp      INTEGER NOT NULL,
    metadata_json  TEXT,
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
);
"""


class GraphStore:
    """In-memory rustworkx graph backed by a SQLite WAL database.

    rustworkx handles traversal; SQLite handles persistence and text search.
    SQLite is the source of truth — the in-memory graph is rebuilt from it on
    every open.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # rustworkx uses integer indices; these dicts bridge to/from our string IDs.
        self._graph: rustworkx.PyDiGraph = rustworkx.PyDiGraph()
        self._id_to_idx: dict[str, int] = {}
        # (source_id, target_id, edge_type_value) → rustworkx edge index
        self._edge_key_to_idx: dict[tuple[str, str, str], int] = {}

        self._db = sqlite3.connect(str(self._db_path))
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA_SQL)
        self._db.commit()

        self._load_from_db()

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """Insert or replace a node in both the graph and SQLite."""
        if node.id in self._id_to_idx:
            idx = self._id_to_idx[node.id]
            self._graph[idx] = node
        else:
            idx = self._graph.add_node(node)
            self._id_to_idx[node.id] = idx

        self._db.execute(
            """
            INSERT OR REPLACE INTO nodes
                (id, type, name, file_path, start_line, end_line, language, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node.id,
                node.type.value,
                node.name,
                node.file_path,
                node.start_line,
                node.end_line,
                node.language,
                json.dumps(node.metadata),
            ),
        )
        self._db.commit()

    def add_edge(self, edge: Edge) -> None:
        """Insert or replace an edge.  Both endpoint nodes must already exist."""
        src_idx = self._id_to_idx.get(edge.source_id)
        tgt_idx = self._id_to_idx.get(edge.target_id)
        if src_idx is None:
            raise ValueError(f"Source node {edge.source_id!r} not found in graph")
        if tgt_idx is None:
            raise ValueError(f"Target node {edge.target_id!r} not found in graph")

        key = (edge.source_id, edge.target_id, edge.type.value)
        if key in self._edge_key_to_idx:
            # Remove the old rustworkx edge so we don't accumulate duplicates.
            self._graph.remove_edge_from_index(self._edge_key_to_idx[key])
            del self._edge_key_to_idx[key]

        edge_idx = self._graph.add_edge(src_idx, tgt_idx, edge)
        self._edge_key_to_idx[key] = edge_idx

        self._db.execute(
            """
            INSERT OR REPLACE INTO edges (source_id, target_id, type, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (
                edge.source_id,
                edge.target_id,
                edge.type.value,
                json.dumps(edge.metadata),
            ),
        )
        self._db.commit()

    def delete_nodes_by_file(self, file_path: str) -> None:
        """Remove all nodes (and their incident edges) that belong to a file."""
        rows = self._db.execute("SELECT id FROM nodes WHERE file_path = ?", (file_path,)).fetchall()
        node_ids = [row["id"] for row in rows]
        if not node_ids:
            return

        node_id_set = set(node_ids)

        # Evict edge-tracking entries whose endpoints are being deleted *before*
        # we call remove_node (which frees those edge indices in rustworkx).
        stale_keys = [
            k for k in self._edge_key_to_idx if k[0] in node_id_set or k[1] in node_id_set
        ]
        for k in stale_keys:
            del self._edge_key_to_idx[k]

        placeholders = ",".join("?" * len(node_ids))
        delete_edges_sql = (
            f"DELETE FROM edges WHERE source_id IN ({placeholders})"
            f" OR target_id IN ({placeholders})"
        )
        self._db.execute(delete_edges_sql, node_ids + node_ids)
        self._db.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", node_ids)
        self._db.commit()

        for node_id in node_ids:
            idx = self._id_to_idx.pop(node_id, None)
            if idx is not None:
                # rustworkx automatically removes incident edges from the graph.
                self._graph.remove_node(idx)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Node | None:
        idx = self._id_to_idx.get(node_id)
        return None if idx is None else self._graph[idx]

    def get_all_nodes(self) -> list[Node]:
        return [self._graph[idx] for idx in self._graph.node_indices()]

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        idx = self._id_to_idx.get(node_id)
        if idx is None:
            return []
        return [data for _, _, data in self._graph.out_edges(idx)]

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        idx = self._id_to_idx.get(node_id)
        if idx is None:
            return []
        return [data for _, _, data in self._graph.in_edges(idx)]

    def search_nodes(
        self,
        query: str,
        node_type: NodeType | None = None,
        language: str | None = None,
    ) -> list[Node]:
        """Case-insensitive substring search over name and file_path."""
        sql = "SELECT id FROM nodes WHERE (name LIKE ? OR file_path LIKE ?)"
        params: list[Any] = [f"%{query}%", f"%{query}%"]
        if node_type is not None:
            sql += " AND type = ?"
            params.append(node_type.value)
        if language is not None:
            sql += " AND language = ?"
            params.append(language)

        rows = self._db.execute(sql, params).fetchall()
        results = []
        for row in rows:
            node = self.get_node(row["id"])
            if node is not None:
                results.append(node)
        return results

    def node_count(self) -> int:
        return len(self._graph)

    def edge_count(self) -> int:
        return self._graph.num_edges()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> GraphStore:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_from_db(self) -> None:
        for row in self._db.execute("SELECT * FROM nodes"):
            node = _row_to_node(row)
            idx = self._graph.add_node(node)
            self._id_to_idx[node.id] = idx

        for row in self._db.execute("SELECT * FROM edges"):
            edge = _row_to_edge(row)
            src_idx = self._id_to_idx.get(edge.source_id)
            tgt_idx = self._id_to_idx.get(edge.target_id)
            if src_idx is not None and tgt_idx is not None:
                edge_idx = self._graph.add_edge(src_idx, tgt_idx, edge)
                key = (edge.source_id, edge.target_id, edge.type.value)
                self._edge_key_to_idx[key] = edge_idx


def _row_to_node(row: sqlite3.Row) -> Node:
    return Node(
        id=row["id"],
        type=NodeType(row["type"]),
        name=row["name"],
        file_path=row["file_path"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        language=row["language"],
        metadata=json.loads(row["metadata"]),
    )


def _row_to_edge(row: sqlite3.Row) -> Edge:
    return Edge(
        source_id=row["source_id"],
        target_id=row["target_id"],
        type=EdgeType(row["type"]),
        metadata=json.loads(row["metadata"]),
    )
