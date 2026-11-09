"""Helpers for the consent page (templates/oauth2_provider/authorize.html)."""

from urllib.parse import urlsplit

from django import template

from accounts.oauth import is_loopback

register = template.Library()


@register.filter
def host(url: str) -> str:
    """https://claude.ai/api/mcp/auth_callback → claude.ai"""
    return urlsplit(url).hostname or url


@register.filter
def loopback(url: str) -> bool:
    return is_loopback(url)
