"""Development aid: log every MCP request and response as it goes over the wire.

An ASGI middleware sees the raw messages the server exchanges with uvicorn,
so this shows exactly what the client sent and what we answered.
"""

import json
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("mcp_tools.wire")


def _pretty(body: bytes) -> str:
    try:
        return json.dumps(json.loads(body), indent=2, ensure_ascii=False)
    except ValueError:
        return body.decode(errors="replace")


def _is_keepalive(body: bytes) -> bool:
    """SSE comment lines (`: ping`) that keep a stream open. Nothing to read."""
    lines = body.strip().splitlines()
    return bool(lines) and all(line.startswith(b":") for line in lines)


class WireLog:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        mcp_headers = {k.decode(): v.decode() for k, v in scope["headers"] if k.lower().startswith(b"mcp-")}
        log.info("→ %s %s %s", scope["method"], scope["path"], mcp_headers or "")

        async def logged_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request" and message.get("body"):
                log.info("→ %s", _pretty(message["body"]))
            return message

        async def logged_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                log.info("← HTTP %s", message["status"])
            elif message["type"] == "http.response.body" and message.get("body"):
                if _is_keepalive(message["body"]):
                    return await send(message)
                log.info("← %s", _pretty(message["body"]))
            await send(message)

        await self.app(scope, logged_receive, logged_send)
