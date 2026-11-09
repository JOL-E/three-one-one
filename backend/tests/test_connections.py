"""Connected apps: what has access, and taking it back (/api/connections)."""

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, RefreshToken
from starlette.testclient import TestClient

from tests.conftest import issue_token
from tests.test_oauth import tools_list

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner() -> User:
    return User.objects.create_user("owner", password="synthetic-pass")


@pytest.fixture
def api(owner: User) -> Client:
    c = Client(enforce_csrf_checks=True)
    c.force_login(owner)
    c.get("/api/auth/csrf")
    c.defaults["HTTP_X_CSRFTOKEN"] = c.cookies["csrftoken"].value
    return c


def app(
    name: str, client_id: str = "", redirect: str = "https://client.example/callback", **kw: Any
) -> Application:
    fields: dict[str, Any] = {
        "name": name,
        "client_type": Application.CLIENT_PUBLIC,
        "authorization_grant_type": Application.GRANT_AUTHORIZATION_CODE,
        "redirect_uris": redirect,
        **kw,
    }
    if client_id:
        fields["client_id"] = client_id
    return Application.objects.create(**fields)


def refresh_token(
    user: User, application: Application, revoked: bool = False, idle: timedelta = timedelta(hours=1)
) -> RefreshToken:
    """A refresh token whose access token expired `idle` ago."""
    issue_token(user, app=application, expires_in=-idle)
    return RefreshToken.objects.create(
        user=user,
        application=application,
        access_token=AccessToken.objects.filter(application=application).latest("id"),
        token_checksum=f"{application.pk:064x}",
        revoked=timezone.now() if revoked else None,
    )


def test_needs_a_session() -> None:
    assert Client().get("/api/connections").status_code == 401


def test_lists_clients_with_a_working_token(api: Client, owner: User) -> None:
    cimd = app(
        "Synthetic CIMD client",
        client_id="https://client.example/metadata.json",
        registration_source=Application.RegistrationSource.CIMD,
    )
    issue_token(owner, app=cimd)
    dcr = app("Synthetic DCR client", redirect="https://other.example/cb")
    refresh_token(owner, dcr)  # access token expired, refresh token still good
    gone = app("Used up")
    refresh_token(owner, gone, revoked=True)
    idle = app("Idle too long")
    refresh_token(owner, idle, idle=timedelta(days=91))  # DOT refuses it after 90 days
    registered_only = app("Never allowed")
    issue_token(None, scope="oauth2_provider:registration", app=registered_only)

    body = api.get("/api/connections").json()
    assert body["mcp_url"] == "http://localhost:8000/mcp"
    assert [(a["name"], a["host"]) for a in body["apps"]] == [
        ("Synthetic DCR client", "other.example"),  # newest token first
        ("Synthetic CIMD client", "client.example"),
    ]


def test_unknown_connection_is_404(api: Client) -> None:
    assert api.delete("/api/connections/999").status_code == 404
    mid_flow = app("Registered, not allowed yet", registration_source=Application.RegistrationSource.DCR)
    assert api.delete(f"/api/connections/{mid_flow.pk}").status_code == 404
    assert Application.objects.filter(pk=mid_flow.pk).exists()  # 404 means nothing changed


def test_disconnect_needs_csrf(owner: User) -> None:
    c = Client(enforce_csrf_checks=True)
    c.force_login(owner)
    client = app("Synthetic client")
    issue_token(owner, app=client)
    assert c.delete(f"/api/connections/{client.pk}").status_code == 403
    assert AccessToken.objects.exists()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_disconnect_ends_access_at_once(api: Client, owner: User, client: TestClient) -> None:
    self_registered = app("Synthetic client", registration_source=Application.RegistrationSource.DCR)
    token = issue_token(owner, app=self_registered)
    refresh_token(owner, self_registered)
    by_hand = app("Added by hand")
    issue_token(owner, app=by_hand)
    assert tools_list(client, token).status_code == 200

    assert api.delete(f"/api/connections/{self_registered.pk}").status_code == 204
    assert tools_list(client, token).status_code == 401
    assert not Application.objects.filter(pk=self_registered.pk).exists()  # registers again

    assert api.delete(f"/api/connections/{by_hand.pk}").status_code == 204
    assert Application.objects.filter(pk=by_hand.pk).exists()  # set up by hand: kept
    assert api.get("/api/connections").json()["apps"] == []
