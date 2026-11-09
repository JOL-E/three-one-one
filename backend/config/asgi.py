"""The app's entry point: one ASGI app with two doors.

`/mcp` goes to the MCP SDK's app, everything else to Django. Run with:
    uvicorn config.asgi:application
"""

import os
from typing import cast

from django.conf import settings
from django.core.asgi import get_asgi_application
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp, Receive, Scope, Send

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Sets up Django; must run before anything imports models.
# The cast: Django's and Starlette's ASGI type hints differ slightly; same protocol.
django_app = cast(ASGIApp, get_asgi_application())

from mcp_tools.server import server  # noqa: E402
from mcp_tools.wire_log import WireLog  # noqa: E402

# DNS-rebinding guard: a web page can point its own domain name at this server's
# address, but its requests still carry that name in Host (and Origin). The SDK
# answers 421 to any Host other than BASE_URL's. In development, any localhost port.
loopback = ["localhost:*", "127.0.0.1:*", "[::1]:*"] if settings.DEBUG else []
guard = TransportSecuritySettings(
    allowed_hosts=[settings.PUBLIC_HOST, *loopback],
    allowed_origins=[settings.BASE_URL, *("http://" + h for h in loopback)],
)

# Stateless + plain JSON: every POST stands alone and gets one JSON answer.
mcp_app: ASGIApp = server.streamable_http_app(
    stateless_http=True, json_response=True, transport_security=guard
)

if settings.DEBUG:
    mcp_app = WireLog(mcp_app)


async def application(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "lifespan":
        # Startup/shutdown events. The MCP app needs them to start its
        # session manager; Django doesn't use them.
        await mcp_app(scope, receive, send)
    elif scope["type"] == "http" and scope["path"] == "/mcp":
        await mcp_app(scope, receive, send)
    else:
        await django_app(scope, receive, send)
