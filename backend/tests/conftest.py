import secrets
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, set_token_value
from starlette.testclient import TestClient

from config.asgi import application


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # `with` sends the startup event, which starts the MCP session manager.
    # The SDK allows that only once per process, hence one client per test run.
    with TestClient(application, base_url="http://localhost:8000") as c:
        yield c


def issue_token(
    user: User | None,
    *,
    scope: str = "mcp",
    resource: list[str] | None = None,
    expires_in: timedelta = timedelta(hours=1),
    app: Application | None = None,
) -> str:
    """An access token as the OAuth flow would store it (hashed); returns the raw value."""
    if app is None:
        app = Application.objects.create(
            name="Synthetic client",
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://client.example/callback",
        )
    raw = secrets.token_urlsafe(30)
    token = AccessToken(
        user=user,
        application=app,
        scope=scope,
        expires=timezone.now() + expires_in,
        resource=resource if resource is not None else [settings.MCP_URL],
    )
    set_token_value(token, raw)
    token.save()
    return raw


@pytest.fixture
def bearer(client: TestClient, db: Any) -> Iterator[str]:
    """Every /mcp request in the test carries a valid token for a synthetic owner."""
    owner = User.objects.create_user("owner", password="synthetic-pass")
    raw = issue_token(owner)
    client.headers["Authorization"] = f"Bearer {raw}"
    yield raw
    del client.headers["Authorization"]
