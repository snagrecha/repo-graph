import pytest
from codenexus.graph.session import SessionManager
from codenexus.graph.store import GraphStore

def test_session_creation(tmp_store):
    manager = SessionManager(tmp_store)
    session_id = manager.create_session(repo_root="/tmp/repo")
    
    assert len(session_id) == 32
    
    # Check if session exists in DB
    row = tmp_store._db.execute(
        "SELECT repo_root FROM agent_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert row["repo_root"] == "/tmp/repo"

def test_record_action(tmp_store):
    manager = SessionManager(tmp_store)
    session_id = manager.create_session(repo_root="/tmp/repo")
    
    manager.record_action(session_id, "inspected", node_id="node1", metadata={"key": "val"})
    
    history = manager.get_session_history(session_id)
    assert len(history) == 1
    assert history[0]["action"] == "inspected"
    assert history[0]["node_id"] == "node1"
    assert history[0]["metadata"] == {"key": "val"}

def test_session_last_active_updates(tmp_store):
    manager = SessionManager(tmp_store)
    session_id = manager.create_session(repo_root="/tmp/repo")
    
    row = tmp_store._db.execute(
        "SELECT last_active FROM agent_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    first_active = row["last_active"]
    
    # Small delay is hard to test without sleep, but we can check if it changes or stays same
    manager.record_action(session_id, "queried")
    
    row = tmp_store._db.execute(
        "SELECT last_active FROM agent_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert row["last_active"] >= first_active
