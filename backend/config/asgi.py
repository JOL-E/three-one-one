"""The app's entry point: one ASGI app with two doors.

`/mcp` goes to the MCP SDK's app, everything else to Django. Run with:
    uvicorn config.asgi:application
"""

import os
from typing import cast

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application
from starlette.types import ASGIApp, Receive, Scope, Send

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Sets up Django; must run before anything imports models.
_django = get_asgi_application()
# In development, also serve static files (the admin's CSS).
# The cast: Django's and Starlette's ASGI type hints differ slightly; same protocol.
django_app = cast(ASGIApp, ASGIStaticFilesHandler(_django) if settings.DEBUG else _django)

from mcp_tools.server import server  # noqa: E402
from mcp_tools.wire_log import WireLog  # noqa: E402

# Stateless + plain JSON: every POST stands alone and gets one JSON answer.
mcp_app: ASGIApp = server.streamable_http_app(stateless_http=True, json_response=True)

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
