"""The client's real IP address, for the login lockout (DECISIONS #48).

Behind a proxy or tunnel every request arrives from the proxy itself, so
REMOTE_ADDR is the same for everyone. CLIENT_IP_HEADER names the header in which
the proxy passes on the real address (`CF-Connecting-IP` behind Cloudflare
Tunnel, `X-Forwarded-For` behind Caddy or nginx). Trust it only if the app
can't be reached except through that proxy: anyone talking to the app directly
could set the header to anything.
"""

from django.conf import settings
from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str | None:
    header: str = settings.CLIENT_IP_HEADER
    if header:
        # Django's spelling of a header in META: "CF-Connecting-IP" -> "HTTP_CF_CONNECTING_IP".
        value: str = request.META.get("HTTP_" + header.upper().replace("-", "_"), "")
        # A forwarding chain is "client, proxy1, proxy2". The last entry is the one
        # our own proxy added; earlier ones came from the client and can be forged.
        address = value.split(",")[-1].strip()
        if address:
            return address
    remote: str | None = request.META.get("REMOTE_ADDR")
    return remote
