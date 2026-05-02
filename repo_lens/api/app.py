from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from repo_lens import __version__
from repo_lens.api.dependencies import init_dependencies
from repo_lens.api.routes import graph as graph_routes
from repo_lens.api.routes import overlays as overlay_routes
from repo_lens.api.websocket import router as ws_router
from repo_lens.graph.store import GraphStore
from repo_lens.mcp.server import create_mcp_server

logger = logging.getLogger(__name__)


class _SentResponse(Response):
    """No-op Response returned after handle_post_message has already written the response."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        pass  # response already written by handle_post_message


def create_app(store: GraphStore, repo_root: str) -> FastAPI:
    init_dependencies(store, repo_root)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from repo_lens.api.watcher import start_watcher

        loop = asyncio.get_running_loop()
        observer = start_watcher(store, repo_root, loop)
        try:
            yield
        finally:
            observer.stop()
            observer.join()

    app = FastAPI(
        title="repo-lens",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # MCP over HTTP/SSE transport
    from mcp.server.sse import SseServerTransport

    sse_transport = SseServerTransport("/mcp/messages")
    mcp_server = create_mcp_server(store, repo_root)

    @app.get("/mcp/sse", include_in_schema=False)
    async def handle_sse(request: Request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )

    @app.post("/mcp/messages", include_in_schema=False)
    async def handle_post_message(request: Request):
        # handle_post_message writes the full ASGI response (headers + body)
        # directly via send, so we return an inert Response to prevent FastAPI
        # from sending a second response on top of it.
        await sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )
        return _SentResponse()

    # REST routes
    app.include_router(graph_routes.router)
    app.include_router(overlay_routes.router)
    app.include_router(ws_router)

    # Serve built React UI if available; otherwise return a placeholder
    # In development, it lives at the repo root. In a PyPI wheel, it's bundled inside repo_lens.
    local_ui = Path(__file__).parent.parent.parent / "ui" / "dist"
    bundled_ui = Path(__file__).parent.parent / "ui"

    if local_ui.is_dir():
        app.mount("/", StaticFiles(directory=str(local_ui), html=True), name="ui")
    elif bundled_ui.is_dir():
        app.mount("/", StaticFiles(directory=str(bundled_ui), html=True), name="ui")
    else:

        @app.get("/", include_in_schema=False)
        async def ui_placeholder():
            return JSONResponse(
                {"status": "ui_not_built", "hint": "cd ui && npm run build"}
            )

    # Phase 2: include routes/timeline.py once diff_snapshot.py is complete

    return app
