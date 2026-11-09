"""OAuth for MCP clients (DECISIONS #11, #46, #49): the whole flow, as Claude runs it.

1. /mcp without a token → 401, pointing to the protected-resource document.
2. That document names the authorization server; its metadata names the endpoints.
3. The client registers (or uses a CIMD URL as its client_id).
4. The browser opens /oauth/authorize/: log in, "Allow" → one-time code.
5. The client swaps code + PKCE verifier for tokens, calls /mcp, refreshes.
"""

import base64
import hashlib
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, RefreshToken
from starlette.testclient import TestClient

from accounts.oauth import REGISTRATIONS_PER_HOUR, prune_unused_clients
from tests.conftest import issue_token

BASE = "http://localhost:8000"
MCP = f"{BASE}/mcp"
CALLBACK = "https://client.example/callback"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_rate_limit() -> None:
    cache.clear()


@pytest.fixture
def owner() -> User:
    return User.objects.create_user("owner", password="synthetic-pass")


def register(c: Client, **metadata: Any) -> Any:
    body = {
        "client_name": "Synthetic client",
        "redirect_uris": [CALLBACK],
        "grant_types": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_method": "none",
        **metadata,
    }
    return c.post("/oauth/register/", body, content_type="application/json")


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(client_id: str, challenge: str, redirect_uri: str | None = CALLBACK) -> str:
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "synthetic-state",
        "scope": "mcp",
        "resource": MCP,
    }
    return "/oauth/authorize/?" + urlencode({k: v for k, v in query.items() if v is not None})


def allow(c: Client, client_id: str, challenge: str, redirect_uri: str = CALLBACK) -> dict[str, list[str]]:
    """Click "Allow" on the consent page; returns the query the client gets back."""
    page = c.get(authorize_url(client_id, challenge, redirect_uri))
    assert page.status_code == 200
    form = {f.name: f.value() or "" for f in page.context["form"] if f.is_hidden}
    response = c.post(authorize_url(client_id, challenge, redirect_uri), {**form, "allow": "on"})
    assert response.status_code == 302
    location = urlsplit(response["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == redirect_uri
    return parse_qs(location.query)


def exchange(c: Client, client_id: str, code: str, verifier: str) -> Any:
    return c.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CALLBACK,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )


def tools_list(client: TestClient, token: str | None) -> Any:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    return client.post("/mcp", json=body, headers=headers)


# --- Discovery -----------------------------------------------------------------


def test_mcp_without_token_points_to_the_resource_document(client: TestClient) -> None:
    response = tools_list(client, None)
    assert response.status_code == 401
    assert (
        f'resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"'
        in (response.headers["WWW-Authenticate"])
    )


def test_resource_document_names_the_issuer() -> None:
    doc = Client().get("/.well-known/oauth-protected-resource/mcp").json()
    assert doc["resource"] == MCP
    assert doc["authorization_servers"] == [BASE]
    assert doc["scopes_supported"] == ["mcp"]


def test_server_metadata_offers_only_the_code_flow() -> None:
    doc = Client().get("/.well-known/oauth-authorization-server").json()
    assert doc["issuer"] == BASE
    assert doc["authorization_endpoint"] == f"{BASE}/oauth/authorize/"
    assert doc["token_endpoint"] == f"{BASE}/oauth/token/"
    assert doc["registration_endpoint"] == f"{BASE}/oauth/register/"
    assert doc["response_types_supported"] == ["code"]
    assert doc["grant_types_supported"] == ["authorization_code", "refresh_token"]
    assert doc["code_challenge_methods_supported"] == ["S256"]
    assert doc["scopes_supported"] == ["mcp"]
    # claude.ai uses a Client ID Metadata Document only if both are advertised.
    assert doc["client_id_metadata_document_supported"] is True
    assert "none" in doc["token_endpoint_auth_methods_supported"]
    assert "introspection_endpoint" not in doc


# --- Registration ----------------------------------------------------------------


def test_registration_gives_a_public_client() -> None:
    response = register(Client())
    assert response.status_code == 201
    body = response.json()
    assert body["token_endpoint_auth_method"] == "none"
    assert "client_secret" not in body
    app = Application.objects.get(client_id=body["client_id"])
    assert app.registration_source == Application.RegistrationSource.DCR


@pytest.mark.parametrize("grant", ["client_credentials", "password", "implicit"])
def test_registration_refuses_other_grant_types(grant: str) -> None:
    response = register(Client(), grant_types=[grant])
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_client_metadata"
    assert not Application.objects.exists()


def test_registration_answers_malformed_grant_types_with_an_error() -> None:
    response = register(Client(), grant_types=[{}])
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_client_metadata"


def test_registration_allows_http_only_to_this_computer() -> None:
    assert register(Client(), redirect_uris=["http://client.example/callback"]).status_code == 400
    assert register(Client(), redirect_uris=["http://localhost/callback"]).status_code == 201
    assert register(Client(), redirect_uris=["http://127.0.0.1/callback"]).status_code == 201


def test_registration_is_rate_limited_per_ip() -> None:
    c = Client(REMOTE_ADDR="203.0.113.7")
    for _ in range(REGISTRATIONS_PER_HOUR):
        assert register(c).status_code == 201
    assert register(c).status_code == 429
    assert register(Client(REMOTE_ADDR="198.51.100.2")).status_code == 201


def test_unused_clients_are_pruned_after_a_day(owner: User) -> None:
    def client(source: str, age: timedelta) -> Application:
        app = Application.objects.create(
            name=source,
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=CALLBACK,
            registration_source=source,
        )
        Application.objects.filter(pk=app.pk).update(created=timezone.now() - age)
        return app

    old_unused = client(Application.RegistrationSource.DCR, timedelta(days=2))
    issue_token(None, scope="oauth2_provider:registration", app=old_unused)  # doesn't count
    old_cimd = client(Application.RegistrationSource.CIMD, timedelta(days=2))
    new_unused = client(Application.RegistrationSource.DCR, timedelta(hours=1))
    old_used = client(Application.RegistrationSource.DCR, timedelta(days=2))
    issue_token(owner, app=old_used)
    by_hand = client(Application.RegistrationSource.MANUAL, timedelta(days=30))

    prune_unused_clients()

    left = set(Application.objects.values_list("pk", flat=True))
    assert left == {new_unused.pk, old_used.pk, by_hand.pk}
    assert old_unused.pk not in left and old_cimd.pk not in left


# --- Authorize, token, /mcp --------------------------------------------------------


def test_authorize_asks_for_login_first() -> None:
    client_id = register(Client()).json()["client_id"]
    url = authorize_url(client_id, pkce()[1])
    response = Client().get(url)
    assert response.status_code == 302
    location = urlsplit(response["Location"])
    assert location.path == "/login/"
    assert parse_qs(location.query)["next"] == [url]  # and back to the same request after


def test_consent_page_shows_where_the_answer_goes(owner: User) -> None:
    c = Client()
    c.force_login(owner)
    client_id = register(c).json()["client_id"]
    page = c.get(authorize_url(client_id, pkce()[1]))
    assert b"Connect Synthetic client?" in page.content
    assert b"client.example" in page.content
    assert b"runs on this computer" not in page.content


def test_loopback_callback_on_any_port_gets_a_warning(owner: User) -> None:
    c = Client()
    c.force_login(owner)
    client_id = register(c, redirect_uris=["http://localhost/callback"]).json()["client_id"]
    # Claude Code listens on a random port; the registered URI has none (RFC 8252).
    page = c.get(authorize_url(client_id, pkce()[1], "http://localhost:54321/callback"))
    assert page.status_code == 200
    assert b"runs on this computer" in page.content


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_full_flow_then_mcp_then_refresh(owner: User, client: TestClient) -> None:
    c = Client()
    c.force_login(owner)
    client_id = register(c).json()["client_id"]
    verifier, challenge = pkce()

    answer = allow(c, client_id, challenge)
    assert answer["state"] == ["synthetic-state"]
    assert answer["iss"] == [BASE]  # RFC 9207: which server answered

    tokens = exchange(Client(), client_id, answer["code"][0], verifier).json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] == 3600
    assert tokens["scope"] == "mcp"

    response = tools_list(client, tokens["access_token"])
    assert response.status_code == 200
    assert "tools" in response.json()["result"]

    # Refresh: new tokens; the old refresh token is spent (rotation).
    refresh = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": tokens["refresh_token"],
    }
    renewed = Client().post("/oauth/token/", refresh).json()
    assert renewed["refresh_token"] != tokens["refresh_token"]
    assert tools_list(client, renewed["access_token"]).status_code == 200
    again = Client().post("/oauth/token/", refresh)
    assert again.status_code == 400
    assert again.json()["error"] == "invalid_grant"
    # ...and the replay revokes what came from it: someone else had a copy.
    assert tools_list(client, renewed["access_token"]).status_code == 401

    # Stored hashed: the database never holds a usable token.
    assert not AccessToken.objects.filter(token=renewed["access_token"]).exists()
    assert not RefreshToken.objects.filter(token=renewed["refresh_token"]).exists()


def test_code_is_useless_without_the_pkce_verifier(owner: User) -> None:
    c = Client()
    c.force_login(owner)
    client_id = register(c).json()["client_id"]
    _, challenge = pkce()
    code = allow(c, client_id, challenge)["code"][0]
    wrong = exchange(Client(), client_id, code, pkce()[0])
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "invalid_grant"


def test_cancel_sends_access_denied(owner: User) -> None:
    c = Client()
    c.force_login(owner)
    client_id = register(c).json()["client_id"]
    challenge = pkce()[1]
    page = c.get(authorize_url(client_id, challenge))
    form = {f.name: f.value() or "" for f in page.context["form"] if f.is_hidden}
    response = c.post(authorize_url(client_id, challenge), form)  # no "allow"
    assert parse_qs(urlsplit(response["Location"]).query)["error"] == ["access_denied"]


def test_http_redirect_elsewhere_is_refused_even_for_a_client_added_by_hand(owner: User) -> None:
    app = Application.objects.create(
        name="By hand",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="http://client.example/callback",
    )
    c = Client()
    c.force_login(owner)
    page = c.get(authorize_url(app.client_id, pkce()[1], "http://client.example/callback"))
    assert page.status_code == 400  # an error page, no redirect to the client
    assert b"Mismatching redirect URI" in page.content

    # Without redirect_uri the client's default is used; the same rule applies.
    page = c.get(authorize_url(app.client_id, pkce()[1], redirect_uri=None))
    assert page.status_code == 400
    assert b"Missing redirect URI" in page.content


def test_no_tokens_without_a_person() -> None:
    """client_credentials would give a token with no user; refused even if a client
    was set up for it by hand."""
    app = Application.objects.create(
        name="By hand",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        client_secret="synthetic-secret",
    )
    response = Client().post(
        "/oauth/token/",
        {"grant_type": "client_credentials", "client_id": app.client_id, "client_secret": "synthetic-secret"},
    )
    assert response.status_code in (400, 401)
    assert not AccessToken.objects.exists()


# --- Which tokens open /mcp ----------------------------------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_mcp_refuses_tokens_that_dont_stand_for_the_owner(owner: User, client: TestClient) -> None:
    good = issue_token(owner)
    assert tools_list(client, good).status_code == 200

    refused = {
        "unknown": "not-a-token",
        "registration token": issue_token(None, scope="oauth2_provider:registration"),
        "other scope": issue_token(owner, scope="read"),
        "expired": issue_token(owner, expires_in=timedelta(seconds=-1)),
        "for another server": issue_token(owner, resource=["https://elsewhere.example/mcp"]),
    }
    for why, token in refused.items():
        assert tools_list(client, token).status_code == 401, why

    owner.is_active = False
    owner.save()
    assert tools_list(client, good).status_code == 401
