"""Connected apps in the app's API (/api/connections): list and disconnect."""

from datetime import datetime

from django.conf import settings
from django.http import Http404, HttpRequest
from ninja import Router, Schema, Status

from . import connections

router = Router(tags=["accounts"])


class ConnectionOut(Schema):
    id: int
    name: str
    host: str
    last_active: datetime


class ConnectionsOut(Schema):
    mcp_url: str  # what to paste into Claude to connect
    apps: list[ConnectionOut]


@router.get("/connections", response=ConnectionsOut)
def list_connections(request: HttpRequest) -> ConnectionsOut:
    apps = [ConnectionOut(**vars(c)) for c in connections.list_connections(request.user)]  # type: ignore[arg-type]
    return ConnectionsOut(mcp_url=settings.MCP_URL, apps=apps)


@router.delete("/connections/{app_id}", response={204: None})
def disconnect(request: HttpRequest, app_id: int) -> Status[None]:
    if not connections.disconnect(request.user, app_id):  # type: ignore[arg-type]
        raise Http404("No such connected app.")
    return Status(204, None)
