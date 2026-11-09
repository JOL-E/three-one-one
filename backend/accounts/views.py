"""Login, logout and the lockout page: server-rendered (DECISIONS #47)."""

from typing import Any

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


class Login(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def locked_out(
    request: HttpRequest, original_response: HttpResponse | None, credentials: Any
) -> HttpResponse:
    """What django-axes shows once an IP + username pair is locked (DECISIONS #48)."""
    minutes = int(settings.AXES_COOLOFF_TIME.total_seconds() // 60)
    return render(request, "accounts/locked.html", {"minutes": minutes}, status=429)
