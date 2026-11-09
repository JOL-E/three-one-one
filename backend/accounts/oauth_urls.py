"""The OAuth endpoints: the part of DOT that MCP clients need, nothing more.

Kept in DOT's URL namespace ("oauth2_provider"), because DOT finds its own
endpoints by name when it writes the metadata. Left out: OpenID Connect, the
device flow, introspection and DOT's application management pages.

    /.well-known/oauth-authorization-server   where the endpoints are (RFC 8414)
    /.well-known/oauth-protected-resource/mcp  who issues tokens for /mcp (RFC 9728)
    /oauth/authorize/      login + "Allow?" page; sends a one-time code back
    /oauth/token/          code (+ PKCE verifier) → tokens; refresh
    /oauth/revoke_token/   a client signing out
    /oauth/register/       automatic client registration (RFC 7591)
"""

from django.urls import path
from oauth2_provider import views

from .oauth import Registration

app_name = "oauth2_provider"

urlpatterns = [
    path(
        ".well-known/oauth-authorization-server",
        views.OAuthServerMetadataView.as_view(),
        name="oauth-server-metadata",
    ),
    path(
        ".well-known/oauth-protected-resource/mcp",
        views.OAuthProtectedResourceMetadataView.as_view(),
        name="oauth-resource-metadata",
    ),
    path("oauth/authorize/", views.AuthorizationView.as_view(), name="authorize"),
    path("oauth/token/", views.TokenView.as_view(), name="token"),
    path("oauth/revoke_token/", views.RevokeTokenView.as_view(), name="revoke-token"),
    path("oauth/register/", Registration.as_view(), name="dcr-register"),
    # RFC 7592: a client reads or deletes its own registration with the token it
    # got at registration. The registration answer links here, so it must exist.
    path(
        "oauth/register/<str:client_id>/",
        views.DynamicClientRegistrationManagementView.as_view(),
        name="dcr-register-management",
    ),
]
