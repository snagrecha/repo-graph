import json
import time
import uuid
from typing import Any

from codenexus.graph.store import GraphStore


class SessionManager:
    """Manages agent session state and action history in the SQLite store."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store
        # Access the underlying sqlite3 connection from GraphStore
        self._db = store._db

    def create_session(self, repo_root: str) -> str:
        """Create a new agent session and return its ID."""
        session_id = uuid.uuid4().hex
        now = int(time.time())
        self._db.execute(
            """
            INSERT INTO agent_sessions (session_id, repo_root, created_at, last_active)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, repo_root, now, now),
        )
        self._db.commit()
        return session_id

    def record_action(
        self,
        session_id: str,
        action: str,
        node_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an agent action in the session history."""
        now = int(time.time())
        self._db.execute(
            """
            INSERT INTO agent_actions (session_id, node_id, action, timestamp, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, node_id, action, now, json.dumps(metadata or {})),
        )
        # Update last_active in session
        self._db.execute(
            "UPDATE agent_sessions SET last_active = ? WHERE session_id = ?",
            (now, session_id),
        )
        self._db.commit()

    def get_session_history(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve the action history for a given session."""
        rows = self._db.execute(
            """
            SELECT node_id, action, timestamp, metadata_json
            FROM agent_actions
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        ).fetchall()

        history = []
        for row in rows:
            history.append(
                {
                    "node_id": row["node_id"],
                    "action": row["action"],
                    "timestamp": row["timestamp"],
                    "metadata": json.loads(row["metadata_json"]),
                }
            )
        return history
