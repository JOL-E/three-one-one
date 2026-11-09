"""Settings for tests and type checking: a fixed key, nothing else changes."""

import os

os.environ.setdefault("SECRET_KEY", "test-only-key")
os.environ.setdefault("BASE_URL", "http://localhost:8000")  # the test client's address

from config.settings import *  # noqa: E402, F403

# Real hashing is deliberately slow; tests log in a lot.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
