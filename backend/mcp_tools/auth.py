"""The bearer check on /mcp: which tokens open the MCP door (DECISIONS #46).

The MCP SDK does the HTTP part: no or a bad token → 401 with a
`WWW-Authenticate` header pointing to /.well-known/oauth-protected-resource/mcp,
which is how a client learns where to get a token. It asks `verify_token` whether
a token is good; the tokens themselves are issued by django-oauth-toolkit
(accounts/oauth.py), so that's where we look them up.
"""

import hashlib

from asgiref.sync import sync_to_async
from django.conf import settings
from mcp.server.auth.provider import AccessToken
from oauth2_provider.models import get_access_token_model

SCOPE = "mcp"


def lookup(raw: str) -> AccessToken | None:
    # Tokens are stored hashed (RFC 9700); DOT finds them by their SHA-256.
    checksum = hashlib.sha256(raw.encode()).hexdigest()
    token = (
        get_access_token_model()
        .objects.select_related("user", "application")
        .filter(token_checksum=checksum)
        .first()
    )
    if token is None or token.application is None:
        return None
    # A token must stand for a person. Registration tokens (one per registered
    # client, for managing its own registration) have no user and another scope.
    if token.user is None or not token.user.is_active:
        return None
    # Not expired, has the mcp scope, and issued for this server's /mcp (RFC 8707;
    # a token issued without naming a resource counts as unrestricted).
    if not token.is_valid([SCOPE]) or not token.allows_audience(settings.MCP_URL):
        return None
    return AccessToken(
        token=raw,
        client_id=token.application.client_id,
        scopes=token.scope.split(),
        expires_at=int(token.expires.timestamp()),
        subject=str(token.user.pk),
    )


class TokenCheck:
    """The SDK's TokenVerifier protocol: one async method."""

    async def verify_token(self, token: str) -> AccessToken | None:
        return await sync_to_async(lookup)(token)
