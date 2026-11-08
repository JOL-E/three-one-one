"""Settings for tests and type checking: a fixed key, nothing else changes."""

import os

os.environ.setdefault("SECRET_KEY", "test-only-key")

from config.settings import *  # noqa: E402, F403
