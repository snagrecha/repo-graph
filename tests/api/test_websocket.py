from __future__ import annotations

import asyncio
import json
import threading

from starlette.testclient import TestClient

from repo_lens.api.websocket import ConnectionManager, manager


def test_websocket_connects_and_receives_broadcast(test_app):
    with TestClient(test_app) as client:
        with client.websocket_connect("/ws/graph") as ws:
            # Broadcast from a background task; TestClient is sync so we use a thread.
            def do_broadcast():
                asyncio.run(manager.broadcast({"type": "update", "node_id": "abc"}))

            t = threading.Thread(target=do_broadcast)
            t.start()
            t.join(timeout=2)

            data = json.loads(ws.receive_text())
            assert data["type"] == "update"
            assert data["node_id"] == "abc"


def test_websocket_disconnect_removes_from_manager(test_app):
    with TestClient(test_app) as client:
        with client.websocket_connect("/ws/graph"):
            assert len(manager.active_connections) > 0

    # After the context exits the connection is cleaned up
    assert len(manager.active_connections) == 0


async def test_multiple_clients_all_receive_broadcast():
    """Test ConnectionManager.broadcast() delivers to all active connections."""
    from unittest.mock import AsyncMock, MagicMock

    ws1 = MagicMock()
    ws1.send_text = AsyncMock()
    ws2 = MagicMock()
    ws2.send_text = AsyncMock()

    mgr = ConnectionManager()
    mgr.active_connections = [ws1, ws2]

    await mgr.broadcast({"type": "ping"})

    ws1.send_text.assert_awaited_once()
    ws2.send_text.assert_awaited_once()
    payload = json.loads(ws1.send_text.call_args[0][0])
    assert payload["type"] == "ping"
