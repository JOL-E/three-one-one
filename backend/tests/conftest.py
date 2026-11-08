from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from config.asgi import application


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # `with` sends the startup event, which starts the MCP session manager.
    # The SDK allows that only once per process, hence one client per test run.
    with TestClient(application, base_url="http://localhost:8000") as c:
        yield c
