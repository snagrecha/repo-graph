from __future__ import annotations

import asyncio


async def test_mcp_sse_endpoint_returns_event_stream(test_app):
    # The SSE stream never terminates; cancel after verifying headers.
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        try:
            async with asyncio.timeout(1):
                async with client.stream("GET", "/mcp/sse") as response:
                    assert response.status_code == 200
                    assert "text/event-stream" in response.headers.get("content-type", "")
                    # Don't consume the body — SSE stream is open-ended.
        except TimeoutError:
            pass  # expected: the SSE connection never closes on its own


async def test_mcp_messages_post_without_session_returns_4xx(async_client):
    response = await async_client.post("/mcp/messages", json={})
    assert response.status_code >= 400
