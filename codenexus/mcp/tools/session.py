from typing import Any

from codenexus.graph.session import SessionManager


def get_agent_session_history(
    session_manager: SessionManager, session_id: str
) -> list[dict[str, Any]]:
    """Return the history of actions for a given session."""
    return session_manager.get_session_history(session_id)


def record_agent_action(
    session_manager: SessionManager,
    session_id: str,
    action: str,
    node_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Record a new action for a given session."""
    session_manager.record_action(
        session_id=session_id, action=action, node_id=node_id, metadata=metadata
    )
    return {"status": "success", "session_id": session_id}
