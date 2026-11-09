"""Connected apps: the MCP clients I've allowed, and taking that back (DECISIONS #11).

A client counts as connected while it holds a token that still works: an access
token that hasn't expired, or a refresh token that hasn't been used up. Rules
live here; accounts/api.py only translates.
"""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_grant_model,
    get_refresh_token_model,
    refresh_token_expire_timedelta,
)


@dataclass(frozen=True)
class Connection:
    id: int
    name: str
    host: str  # who it is: the CIMD document's host, or where its answers go
    last_active: datetime  # when it last got a token: at connecting, then ~hourly while in use


def _host(app: object) -> str:
    client_id: str = getattr(app, "client_id", "")
    if client_id.startswith("https://"):  # CIMD: the client_id is its document's URL
        return urlsplit(client_id).hostname or client_id
    redirect_uris: str = getattr(app, "redirect_uris", "")
    first = redirect_uris.split()[0] if redirect_uris.split() else ""
    return urlsplit(first).hostname or ""


def list_connections(user: AbstractBaseUser) -> list[Connection]:
    now = timezone.now()
    newest: dict[int, datetime] = {}
    live = [
        get_access_token_model().objects.filter(user=user, expires__gt=now),
        # DOT's rule for a refresh token that still works: not revoked, and its access
        # token expired less than REFRESH_TOKEN_EXPIRE_SECONDS ago.
        get_refresh_token_model().objects.filter(
            user=user, revoked__isnull=True, access_token__expires__gt=now - refresh_token_expire_timedelta()
        ),
    ]
    for tokens in live:
        for app_id, created in tokens.values_list("application_id", "created"):
            if app_id is not None and (app_id not in newest or created > newest[app_id]):
                newest[app_id] = created
    apps = get_application_model().objects.filter(id__in=newest)
    connections = [Connection(app.id, app.name or "Unnamed app", _host(app), newest[app.id]) for app in apps]
    return sorted(connections, key=lambda c: c.last_active, reverse=True)


@transaction.atomic
def disconnect(user: AbstractBaseUser, app_id: int) -> bool:
    """End a client's access at once: its tokens and pending codes go. A client that
    registered itself (DCR, CIMD) goes too; it registers again when reconnecting.
    False if there was nothing to disconnect."""
    found = False
    for model in (get_access_token_model(), get_refresh_token_model(), get_grant_model()):
        deleted, _ = model.objects.filter(user=user, application_id=app_id).delete()
        found = found or deleted > 0
    application_model = get_application_model()
    self_registered = [application_model.RegistrationSource.DCR, application_model.RegistrationSource.CIMD]
    if found:
        application_model.objects.filter(id=app_id, registration_source__in=self_registered).delete()
    return found
