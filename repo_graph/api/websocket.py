from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections = [
            ws for ws in self.active_connections if ws is not websocket
        ]

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws/graph")
async def websocket_graph(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Drain any client messages; we don't act on them in Phase 1.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
