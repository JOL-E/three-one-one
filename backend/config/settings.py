"""Django settings. Everything installation-specific comes from the environment."""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DEBUG", "0") == "1"

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set SECRET_KEY (or DEBUG=1 for local development).")
    SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# The app's public address, e.g. https://311.example.com. MCP clients see it in
# the OAuth documents, so it can't be guessed from each request (DECISIONS #12).
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
if not BASE_URL:
    if not DEBUG:
        raise ImproperlyConfigured("Set BASE_URL (or DEBUG=1 for local development).")
    BASE_URL = "http://localhost:8000"
MCP_URL = BASE_URL + "/mcp"  # what OAuth calls the "resource" a token is for

# Where the SQLite file lives. A Docker volume in production.
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)  # SQLite creates the file, not the folder

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",  # for its docs page and `manage.py export_openapi_schema`
    "axes",
    "accounts",  # before oauth2_provider: its templates replace DOT's
    "oauth2_provider",
    "inbox",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",  # last: turns a lockout into the lockout page
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "311.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# --- Login (DECISIONS #47, #48) -------------------------------------------------

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days: logging in on the phone is rare

# The axes backend comes first: it refuses a locked-out IP + username before the
# password is even checked. It counts failures from every login, the admin's too.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]  # the pair, not either alone
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "accounts.views.locked_out"
AXES_CLIENT_IP_CALLABLE = "accounts.client_ip.client_ip"
# Behind a proxy or tunnel: the header carrying the real client IP, e.g.
# CF-Connecting-IP (Cloudflare Tunnel) or X-Forwarded-For (Caddy, nginx).
# Empty: the direct connection's address. See accounts/client_ip.py.
CLIENT_IP_HEADER = os.environ.get("CLIENT_IP_HEADER", "")

# --- OAuth for MCP clients: django-oauth-toolkit (DECISIONS #11, #46, #49) -------
# The app is the authorization server (it issues tokens at /oauth/...) and the
# resource server (/mcp accepts them). See accounts/oauth.py and mcp_tools/auth.py.

OAUTH2_PROVIDER = {
    # The issuer. The name says OIDC, but DOT also builds every endpoint URL in
    # the metadata from it; without it they'd come from each request's Host header.
    "OIDC_ISS_ENDPOINT": BASE_URL,
    "SCOPES": {"mcp": "Read and change your projects and items"},
    "DEFAULT_SCOPES": ["mcp"],
    "OAUTH2_VALIDATOR_CLASS": "accounts.oauth.Validator",
    "PKCE_REQUIRED": True,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 60 * 60,  # 1 hour; clients refresh on their own
    "REFRESH_TOKEN_EXPIRE_SECONDS": 60 * 60 * 24 * 90,  # 90 days unused → connect again
    "ROTATE_REFRESH_TOKEN": True,  # each refresh token works once
    # A spent refresh token coming back means someone else has a copy: revoke the
    # tokens that came from it too. That client has to connect again.
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "REQUEST_APPROVAL_PROMPT": "force",  # always ask, even for a client seen before
    # Automatic registration (DCR) and Client ID Metadata Documents (CIMD), open to
    # any client: registering grants nothing without my login and "Allow".
    "DCR_ENABLED": True,
    "DCR_REGISTRATION_PERMISSION_CLASSES": ("oauth2_provider.dcr.AllowAllDCRPermission",),
    "CIMD_ENABLED": True,
    # Claude Code's callback is http://localhost:<any port>/callback. "http" can't be
    # limited to loopback here; accounts.oauth.Validator refuses every other http URL.
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https", "http"],
    "ALLOW_LOCALHOST_LOOPBACK": True,
    # What the metadata advertises: only what the server accepts.
    "OAUTH2_RESPONSE_TYPES_SUPPORTED": ["code"],
    "OAUTH2_GRANT_TYPES_SUPPORTED": ["authorization_code", "refresh_token"],
    # "none" = public clients (no secret). claude.ai uses CIMD only if it's listed.
    "OAUTH2_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED": ["none", "client_secret_basic", "client_secret_post"],
    "OAUTH2_PROTECTED_RESOURCE_IDENTIFIER": MCP_URL,
    "OAUTH2_PROTECTED_RESOURCE_AUTHORIZATION_SERVERS": [BASE_URL],
    "OAUTH2_PROTECTED_RESOURCE_NAME": "311",
    # RFC 9700 (OAuth security best practice): adopt now what DOT 4.0 will default to.
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,  # S256 only, no "plain"
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,  # header only, never in a URL
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,  # tokens stored hashed
    "COMPLIANT_BCP_RFC9700_REFRESH_TOKEN": True,
    "COMPLIANT_BCP_RFC9700_REDIRECT_URI_MATCHING": True,
    "COMPLIANT_BCP_RFC9700_PKCE_REQUIRED": True,
}
# "http redirect URIs are allowed": only to this computer, see accounts.oauth.Validator.
SILENCED_SYSTEM_CHECKS = ["oauth2_provider.W008"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# In development, print every MCP message (see mcp_tools/wire_log.py).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "mcp_tools.wire": {
            "handlers": ["console"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
    },
}
