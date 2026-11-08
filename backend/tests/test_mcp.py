"""End to end over HTTP: JSON-RPC in, JSON-RPC out, through the real ASGI app."""

import json
import uuid
from typing import Any

import pytest
from starlette.testclient import TestClient

from inbox import services
from inbox.models import Item, Project

# transaction=True: the MCP app runs the services in another thread, which must see
# committed data. serialized_rollback restores the General project after the flush.
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)

TOOLS = {
    "list_projects",
    "list_items",
    "get_item",
    "add_item",
    "update_item",
    "set_status",
    "move_item",
    "add_comment",
    "create_project",
    "update_project",
    "reorder_items",
}


def post(client: TestClient, method: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    response: dict[str, Any] = client.post("/mcp", json=body, headers=headers).json()
    return response


def rpc(client: TestClient, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """The 2025-11-25 revision: no per-request envelope."""
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    result: dict[str, Any] = post(client, method, params or {}, headers)["result"]
    return result


def call(client: TestClient, tool: str, **arguments: Any) -> Any:
    """Call a tool; return the parsed JSON text, or the raw result if it's an error."""
    result = rpc(client, "tools/call", {"name": tool, "arguments": arguments})
    if result["isError"]:
        return result
    text = result["content"][0]["text"]
    return json.loads(text) if text[:1] in "[{" else text


def test_tools_list_has_no_output_schemas(client: TestClient) -> None:
    tools = {t["name"]: t for t in rpc(client, "tools/list")["tools"]}
    assert set(tools) == TOOLS  # DECISIONS #7: no delete, no project state change
    assert not any("outputSchema" in t for t in tools.values())
    # Filled by the server from the user's answer, never by Claude.
    assert "confirmation" not in tools["reorder_items"]["inputSchema"]["properties"]
    # Generated labels are stripped; a property named "title" stays.
    assert '"title": "' not in json.dumps(tools)
    assert "title" in tools["add_item"]["inputSchema"]["properties"]


def test_initialize_sends_instructions(client: TestClient) -> None:
    result = rpc(
        client,
        "initialize",
        {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    )
    assert "status change needs a short comment" in result["instructions"]


def test_capture_sort_and_work_an_item(client: TestClient) -> None:
    added = call(client, "add_item", title="Synthetic idea", details="notes")
    assert "project" not in added  # empty fields are left out: no project = inbox
    assert [i["title"] for i in call(client, "list_items")] == ["Synthetic idea"]

    project = call(client, "create_project", name="Synthetic project")
    assert project["state"] == "idea"
    call(client, "move_item", item_id=added["id"], project_id=project["id"])
    call(client, "set_status", item_id=added["id"], status="doing", comment="Starting")
    call(client, "add_comment", item_id=added["id"], text="Halfway")

    item = call(client, "get_item", item_id=added["id"])
    assert (item["project"], item["status"]) == ("Synthetic project", "doing")
    assert [(a["kind"], a["author"]) for a in item["activity"]] == [
        ("created", "claude"),
        ("moved", "claude"),
        ("status", "claude"),
        ("comment", "claude"),
    ]
    assert call(client, "list_items") == []  # inbox is empty now


def test_search_says_where_each_item_is(client: TestClient) -> None:
    project = services.create_project("Synthetic project")
    services.add_item("Lint Dockerfiles", project_id=project.id)
    services.add_item("Dockerfile notes")
    found = call(client, "list_items", search="dockerfile")
    assert [(i["title"], i["project"]) for i in found] == [
        ("Dockerfile notes", "Inbox"),
        ("Lint Dockerfiles", "Synthetic project"),
    ]


def test_done_items_hidden_unless_asked(client: TestClient) -> None:
    project = services.create_project("Synthetic")
    item = services.add_item("x", project_id=project.id)
    call(client, "set_status", item_id=str(item.id), status="done", comment="Shipped")
    assert call(client, "list_items", project_id=str(project.id)) == []
    assert len(call(client, "list_items", project_id=str(project.id), include_done=True)) == 1


def test_rule_violation_reaches_claude_as_tool_error(client: TestClient) -> None:
    result = call(client, "add_item", title=" ")
    assert result["isError"] is True
    assert "needs a title" in result["content"][0]["text"]


def test_status_change_without_comment_is_refused(client: TestClient) -> None:
    item = services.add_item("x", project_id=services.general_project().id)
    result = call(client, "set_status", item_id=str(item.id), status="doing", comment="  ")
    assert "needs a comment" in result["content"][0]["text"]


def test_django_still_serves_everything_else(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


# --- reorder_items: asks the user through elicitation (2026-07-28 revision) ---

ENVELOPE = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "0"},
}
CAN_ELICIT: dict[str, Any] = {"elicitation": {"form": {}}}


def reorder(
    client: TestClient, args: dict[str, Any], capabilities: dict[str, Any], **retry: Any
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/call",
        "Mcp-Name": "reorder_items",
    }
    meta = {**ENVELOPE, "io.modelcontextprotocol/clientCapabilities": capabilities}
    params = {"name": "reorder_items", "arguments": args, "_meta": meta, **retry}
    return post(client, "tools/call", params, headers)


@pytest.fixture
def ranked() -> tuple[Project, list[Item]]:
    project = services.create_project("Synthetic")
    return project, [services.add_item(t, project_id=project.id) for t in "ab"]


def reversed_args(ranked: tuple[Project, list[Item]]) -> dict[str, Any]:
    project, items = ranked
    return {"project_id": str(project.id), "item_ids": [str(i.id) for i in reversed(items)]}


def order(project: Project) -> list[str]:
    return [i.title for i in services.list_project_items(project.id)]


def answer(client: TestClient, args: dict[str, Any], action: str) -> dict[str, Any]:
    first = reorder(client, args, CAN_ELICIT)["result"]
    assert first["resultType"] == "input_required"
    [(key, request)] = first["inputRequests"].items()
    assert request["params"]["message"].endswith("1. b\n2. a")
    second: dict[str, Any] = reorder(
        client,
        args,
        CAN_ELICIT,
        inputResponses={key: {"action": action, "content": {}}},
        requestState=first["requestState"],
    )["result"]
    return second


def test_reorder_happens_only_after_user_accepts(client: TestClient, ranked: Any) -> None:
    project, _ = ranked
    result = answer(client, reversed_args(ranked), "accept")
    assert result["isError"] is False
    assert result["content"][0]["text"].startswith("The user confirmed.")
    assert order(project) == ["b", "a"]


def test_reorder_declined_changes_nothing(client: TestClient, ranked: Any) -> None:
    project, _ = ranked
    result = answer(client, reversed_args(ranked), "decline")
    assert result["isError"] is True
    assert "did not confirm" in result["content"][0]["text"]
    assert order(project) == ["a", "b"]


def test_reorder_refused_when_client_cannot_ask(client: TestClient, ranked: Any) -> None:
    project, _ = ranked
    error = reorder(client, reversed_args(ranked), capabilities={})["error"]
    assert error["code"] == -32021  # missing required client capability
    assert order(project) == ["a", "b"]


def test_invalid_order_refused_before_asking(client: TestClient, ranked: Any) -> None:
    args = reversed_args(ranked)
    args["item_ids"] = args["item_ids"][:1]
    result = reorder(client, args, CAN_ELICIT)["result"]
    assert result["isError"] is True
    assert "exactly once" in result["content"][0]["text"]


# --- Short ids (DECISIONS #40) and project edits (#37) -----------------------


def test_results_use_short_ids_and_tools_accept_them(client: TestClient) -> None:
    item = services.add_item("Synthetic idea")
    listed = call(client, "list_items")[0]
    assert listed["id"] == item.id.hex[:4].upper()
    call(client, "add_comment", item_id=f"#{listed['id'].lower()}", text="Found it by short id")
    assert item.activities.count() == 2


def test_ambiguous_short_id_is_refused_naming_the_candidates(client: TestClient) -> None:
    a = services.add_item("First", item_id=uuid.UUID("3f9a0000-0000-4000-8000-000000000001"))
    services.add_item("Second", item_id=uuid.UUID("3f9a1000-0000-4000-8000-000000000002"))
    result = call(client, "get_item", item_id="3F9A")
    assert result["isError"] is True
    assert "3F9A0 (First)" in result["content"][0]["text"]
    assert call(client, "get_item", item_id="3F9A0")["title"] == a.title


def test_claude_can_edit_a_project_but_not_its_state(client: TestClient) -> None:
    project = services.create_project("Synthetic")
    edited = call(client, "update_project", project_id=str(project.id), name="Renamed", repo_url="")
    assert (edited["name"], edited["state"]) == ("Renamed", "idea")
    tools = {t["name"]: t for t in rpc(client, "tools/list")["tools"]}
    assert "state" not in tools["update_project"]["inputSchema"]["properties"]
