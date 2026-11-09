from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.views import LogoutView
from django.http import HttpRequest, HttpResponse
from django.urls import include, path, re_path
from ninja import NinjaAPI
from ninja.security import django_auth

from accounts.api import router as accounts_router
from accounts.views import Login
from config.frontend import app_shell
from inbox.api import router as inbox_router
from inbox.services import NotFound, RuleViolation

# Every endpoint needs a session (and CSRF on writes) unless it says auth=None.
# The interactive docs at /api/docs are for logged-in staff only.
api = NinjaAPI(title="311", version="1", auth=django_auth, docs_decorator=staff_member_required)


@api.exception_handler(RuleViolation)
def rule_violation(request: HttpRequest, exc: RuleViolation) -> HttpResponse:
    """A broken rule's message goes to the app as is: `{"detail": "..."}`."""
    status = 404 if isinstance(exc, NotFound) else 400
    return api.create_response(request, {"detail": str(exc)}, status=status)


@api.get("/health", auth=None)
def health(request: HttpRequest) -> dict[str, str]:
    return {"status": "ok"}


api.add_router("/", inbox_router)
api.add_router("/", accounts_router)

urlpatterns = [
    path("login/", Login.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),  # POST only
    path("", include("accounts.oauth_urls")),  # /.well-known/… and /oauth/…
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    # Last: any other path is a screen of the app. The server's own prefixes stay
    # out, so a wrong /api/ or /oauth/ URL gets a real 404, not the app.
    re_path(r"^(?!(?:api|admin|static|oauth|login|logout|mcp|\.well-known)(?:/|$)).*$", app_shell),
]
