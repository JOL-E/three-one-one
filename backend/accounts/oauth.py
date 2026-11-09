"""Where 311 narrows django-oauth-toolkit (DOT) to what an MCP client needs.

DOT is a general OAuth server: it can also hand out tokens without a user
(`client_credentials`) or for a typed-in password (`password`). For MCP only one
flow makes sense, the authorization code flow with PKCE, where I log in and
click "Allow". Everything here enforces that, on the server (CLAUDE.md:
rules are enforced by the server).

- `Validator`: the token and authorize endpoints accept only that flow, and
  plain-http redirects only to this computer (Claude Code's callback).
- `Registration`: automatic client registration with a rate limit, the same
  rules, and cleanup of clients that never got a token (DECISIONS #49).
- `MetadataFetcher`: reads a client's CIMD document, ignoring grant types this
  server doesn't offer (DECISIONS #57).
"""

import json
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from oauth2_provider.cimd import SafeMetadataFetcher
from oauth2_provider.models import (
    clear_expired,
    get_access_token_model,
    get_application_model,
    get_refresh_token_model,
)
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.views import DynamicClientRegistrationView

from .client_ip import client_ip

GRANT_TYPES = {"authorization_code", "refresh_token"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

REGISTRATIONS_PER_HOUR = 10  # per IP; a client registers once per connection
UNUSED_CLIENT_TTL = timedelta(days=1)


def is_loopback(uri: str) -> bool:
    """A redirect back to this computer, like Claude Code's http://localhost:<port>/callback."""
    return urlsplit(uri).hostname in LOOPBACK_HOSTS


def redirect_allowed(uri: str) -> bool:
    """https anywhere, plain http only to this computer: a code sent over http to
    another machine could be read on the way."""
    scheme = urlsplit(uri).scheme
    return scheme == "https" or (scheme == "http" and is_loopback(uri))


class Validator(OAuth2Validator):  # type: ignore[misc]  # untyped base
    """DOT's checks plus ours. oauthlib calls these while handling each request."""

    def validate_grant_type(
        self, client_id: str, grant_type: str, client: Any, request: Any, *args: Any, **kwargs: Any
    ) -> bool:
        return grant_type in GRANT_TYPES and bool(
            super().validate_grant_type(client_id, grant_type, client, request, *args, **kwargs)
        )

    def validate_redirect_uri(
        self, client_id: str, redirect_uri: str, request: Any, *args: Any, **kwargs: Any
    ) -> bool:
        return redirect_allowed(redirect_uri) and bool(
            super().validate_redirect_uri(client_id, redirect_uri, request, *args, **kwargs)
        )

    def get_default_redirect_uri(self, client_id: str, request: Any, *args: Any, **kwargs: Any) -> str | None:
        """Used instead of validate_redirect_uri when the request names no redirect_uri,
        so the same rule applies here. None makes oauthlib refuse the request."""
        uri = super().get_default_redirect_uri(client_id, request, *args, **kwargs)
        return uri if isinstance(uri, str) and redirect_allowed(uri) else None


class MetadataFetcher(SafeMetadataFetcher):  # type: ignore[misc]  # untyped base
    """DOT's safe fetcher (no internal addresses, size and time limits), but it
    drops grant types this server doesn't offer before DOT validates the document.

    DOT stores one grant type per client and refuses a document that lists two
    besides refresh_token. claude.ai's lists authorization_code and jwt-bearer,
    which we don't offer; a server may ignore those (RFC 7591, section 2).
    A document left with no usable grant type is still refused by DOT.
    Delete this once DOT handles such documents itself.
    """

    def fetch(self, client_id: str) -> tuple[Any, int]:
        metadata, max_age = super().fetch(client_id)
        grant_types = metadata.get("grant_types")
        if isinstance(grant_types, list) and all(isinstance(g, str) for g in grant_types):
            metadata["grant_types"] = [g for g in grant_types if g in GRANT_TYPES]
        return metadata, max_age


def prune_unused_clients() -> int:
    """Delete registered clients that never got a token, plus expired tokens.

    Every new connection from claude.ai registers a new client, and some never
    finish (closed tab, "Cancel"). Runs with registrations (at most hourly), so nothing needs a
    scheduler. Clients added by hand in the admin are never touched.
    """
    clear_expired()
    application_model = get_application_model()
    # application_id can be NULL; one NULL in a NOT IN list would keep every client.
    tokens = get_access_token_model().objects.filter(user__isnull=False, application__isnull=False)
    refresh_tokens = get_refresh_token_model().objects.filter(application__isnull=False)
    stale = application_model.objects.filter(
        registration_source__in=[
            application_model.RegistrationSource.DCR,
            application_model.RegistrationSource.CIMD,
        ],
        created__lt=timezone.now() - UNUSED_CLIENT_TTL,
    ).exclude(Q(id__in=tokens.values("application_id")) | Q(id__in=refresh_tokens.values("application_id")))
    deleted: int = stale.delete()[0]
    return deleted


def refusal(description: str, status: int = 400) -> JsonResponse:
    """An RFC 7591 error, the same shape DOT uses."""
    return JsonResponse({"error": "invalid_client_metadata", "error_description": description}, status=status)


class Registration(DynamicClientRegistrationView):  # type: ignore[misc]  # untyped base
    """POST /oauth/register/: DOT's registration view behind our checks."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        key = f"oauth-register:{client_ip(request)}"
        # Counted per process (Django's default cache): fine for one worker.
        cache.add(key, 0, timeout=60 * 60)  # the window starts with the first try
        try:
            count = cache.incr(key)
        except ValueError:  # the window ended between add and incr
            cache.set(key, count := 1, timeout=60 * 60)
        if count > REGISTRATIONS_PER_HOUR:
            too_many = JsonResponse(
                {"error": "slow_down", "error_description": "Too many registrations. Try again later."},
                status=429,
            )
            too_many["Retry-After"] = "3600"
            return too_many

        try:
            data = json.loads(request.body)
        except ValueError:
            data = None  # DOT answers malformed JSON itself
        if isinstance(data, dict):
            grant_types = data.get("grant_types", ["authorization_code"])
            if isinstance(grant_types, list) and not all(
                isinstance(g, str) and g in GRANT_TYPES for g in grant_types
            ):
                return refusal("Only the authorization_code and refresh_token grant types are supported.")
            redirect_uris = data.get("redirect_uris", [])
            if isinstance(redirect_uris, list) and not all(
                isinstance(u, str) and redirect_allowed(u) for u in redirect_uris
            ):
                return refusal("Redirect URIs must use https, or http to localhost.")

        if cache.add("oauth-prune", 1, timeout=60 * 60):  # at most hourly: anyone can register
            prune_unused_clients()
        response: HttpResponse = super().post(request, *args, **kwargs)
        return response
