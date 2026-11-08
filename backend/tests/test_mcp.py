"""End to end over HTTP: JSON-RPC in, JSON-RPC out, through the real ASGI app."""

from typing import Any

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.django_db(transaction=True)

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-11-25",
}


def rpc(client: TestClient, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    response = client.post("/mcp", json=body, headers=HEADERS)
    assert response.status_code == 200
    result: dict[str, Any] = response.json()["result"]
    return result


def test_tools_list(client: TestClient) -> None:
    names = {tool["name"] for tool in rpc(client, "tools/list")["tools"]}
    assert names == {"list_items", "add_item"}


def test_add_then_list(client: TestClient) -> None:
    added = rpc(client, "tools/call", {"name": "add_item", "arguments": {"title": "Synthetic idea"}})
    assert added["isError"] is False
    assert added["structuredContent"]["title"] == "Synthetic idea"

    listed = rpc(client, "tools/call", {"name": "list_items", "arguments": {}})
    assert [i["title"] for i in listed["structuredContent"]["result"]] == ["Synthetic idea"]


def test_rule_violation_reaches_claude_as_tool_error(client: TestClient) -> None:
    result = rpc(client, "tools/call", {"name": "add_item", "arguments": {"title": " "}})
    assert result["isError"] is True
    assert "needs a title" in result["content"][0]["text"]


def test_django_still_serves_everything_else(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
