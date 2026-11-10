"""The MCP server: which tools Claude sees, and how they map to the services.

The SDK builds each tool's JSON Schema (`inputSchema` in `tools/list`) from the
function's type hints, and its description from the docstring. Tools stay thin:
they translate between MCP and the services layer, nothing more.

Results are plain text holding compact JSON, without an `outputSchema`
(DECISIONS #31): the schema would double or triple every tool's size in
`tools/list`, and Claude reads the text either way.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from asgiref.sync import sync_to_async
from django.conf import settings
from mcp.server.auth.settings import AuthSettings
from mcp.server.elicitation import AcceptedElicitation, ElicitationResult
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.resolve import Elicit, Resolve
from mcp_types import Tool, ToolAnnotations
from mcp_types.version import is_version_at_least
from pydantic import AnyHttpUrl, BaseModel, Field, TypeAdapter

from inbox import services
from inbox.models import Activity, Author, Item, ItemStatus, Project
from mcp_tools.auth import SCOPE, TokenCheck

INSTRUCTIONS = """\
311 is the user's inbox for side-project ideas and the work on them.

- Projects have a state: idea, building, live or archived. "General" is a
  permanent project for things to look into or try that will never be their own project.
- An item belongs to a project or sits in the inbox (no project yet). Its status
  is open, doing or done; inbox items are always open.
- Items have short ids like 3F9A; the user sees the same ids in the app (#3F9A).
- A project's open and doing items are in priority order, top first. The user sets it.
- When the user mentions an idea or task worth keeping, add it. It goes to the
  inbox unless the user names a project.
- Every status change needs a short comment saying why; it is kept in the item's
  activity log. Use add_comment to record progress, decisions or findings.
- You can't delete anything or change a project's state. Ask the user to do that in the app.
"""


def without_titles(schema: Any) -> Any:
    """Drop the `"title": "Project Id"`-style labels pydantic adds to every schema.

    They repeat the property names and cost context in every conversation. Only
    string values are dropped, so a property *named* title (a dict) stays.
    """
    if isinstance(schema, dict):
        return {k: without_titles(v) for k, v in schema.items() if not (k == "title" and isinstance(v, str))}
    if isinstance(schema, list):
        return [without_titles(v) for v in schema]
    return schema


class Server(MCPServer):
    async def list_tools(self) -> list[Tool]:
        # The SDK answers `tools/list` through this method.
        tools = await super().list_tools()
        return [t.model_copy(update={"input_schema": without_titles(t.input_schema)}) for t in tools]


# Every request to /mcp needs a token with the mcp scope (mcp_tools/auth.py).
# The SDK also offers a protected-resource document from these settings, but
# config/asgi.py sends only /mcp to the SDK; Django serves that document
# (accounts/oauth_urls.py), from the same BASE_URL.
auth = AuthSettings(
    issuer_url=AnyHttpUrl(settings.BASE_URL),
    resource_server_url=AnyHttpUrl(settings.MCP_URL),
    required_scopes=[SCOPE],
    validate_token_resource=False,  # TokenCheck checks the resource itself
)
server = Server(
    name="311", version="0.1.0", instructions=INSTRUCTIONS, token_verifier=TokenCheck(), auth=auth
)

ProjectId = Annotated[UUID, Field(description="A project's id, from list_projects.")]
ItemId = Annotated[str, Field(description="An item's id, like 3F9A.")]


def tool(*, read_only: bool = False, destructive: bool = False) -> Callable[[Callable[..., object]], object]:
    """Register a tool with plain-text output and annotations.

    Annotations are hints for clients (e.g. whether to ask before calling); the
    server never relies on them. Everything here touches only this app's data,
    hence `open_world_hint=False`.
    """
    annotations = ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=None if read_only else destructive,
        open_world_hint=False,
    )
    return server.tool(annotations=annotations, structured_output=False)


async def run[**P, R](fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """Call a sync service from an async tool; a broken rule becomes a tool error.

    sync_to_async runs the service in a worker thread (services are sync, see
    services.py). ToolError's message reaches Claude as an `isError: true` result.
    """
    try:
        return await sync_to_async(fn)(*args, **kwargs)
    except services.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


async def resolve(ref: str) -> Item:
    """An item from a short id ("3F9A") or a full one (DECISIONS #40)."""
    return await run(services.resolve_item, ref)


def _resolve_all(refs: list[str]) -> list[UUID]:
    return [services.resolve_item(ref).id for ref in refs]


# --- What the tools return ---------------------------------------------------


class ProjectOut(BaseModel):
    id: UUID
    name: str
    state: str
    description: str | None = None
    repo_url: str | None = None

    @classmethod
    def of(cls, p: Project) -> ProjectOut:
        return cls(
            id=p.id,
            name=p.name,
            state=p.state,
            description=p.description or None,
            repo_url=p.repo_url or None,
        )


class ItemSummary(BaseModel):
    id: str  # short id (DECISIONS #40); saves context and matches what the user sees
    title: str
    status: str
    project: str | None = None  # only in search results; "Inbox" if none

    @classmethod
    def of(cls, i: Item, ids: dict[UUID, str], with_project: bool = False) -> ItemSummary:
        project = (i.project.name if i.project else "Inbox") if with_project else None
        return cls(id=ids[i.id], title=i.title, status=i.status, project=project)


class ActivityOut(BaseModel):
    at: datetime
    author: str
    kind: str
    text: str | None = None
    change: str | None = None

    @classmethod
    def of(cls, a: Activity) -> ActivityOut:
        change = f"{a.old_value} -> {a.new_value}" if a.old_value or a.new_value else None
        return cls(at=a.created_at, author=a.author, kind=a.kind, text=a.text or None, change=change)


class ItemOut(BaseModel):
    id: str
    title: str
    details: str | None = None
    status: str
    project: str | None = Field(None, description="Project name; none = inbox.")
    created_at: datetime
    done_at: datetime | None = None
    activity: list[ActivityOut] | None = None

    @classmethod
    def of(cls, i: Item, ids: dict[UUID, str], activity: list[Activity] | None = None) -> ItemOut:
        return cls(
            id=ids[i.id],
            title=i.title,
            details=i.details or None,
            status=i.status,
            project=i.project.name if i.project else None,
            created_at=i.created_at,
            done_at=i.done_at,
            activity=[ActivityOut.of(a) for a in activity] if activity is not None else None,
        )


def as_text(value: BaseModel | list[ProjectOut] | list[ItemSummary]) -> str:
    """Compact JSON; empty fields left out to save context."""
    adapter: TypeAdapter[object] = TypeAdapter(type(value))
    return adapter.dump_json(value, exclude_none=True).decode()


# --- Reading -----------------------------------------------------------------


@tool(read_only=True)
async def list_projects(include_archived: bool = False) -> str:
    """List projects with their ids. Archived projects only if include_archived."""
    projects = await run(services.list_projects, include_archived)
    return as_text([ProjectOut.of(p) for p in projects])


@tool(read_only=True)
async def list_items(
    project_id: Annotated[UUID | None, Field(description="Omit to list the inbox.")] = None,
    search: Annotated[
        str | None,
        Field(
            description="Words in the title, or the start of an item id. "
            "Searches the inbox and every project; project_id is ignored."
        ),
    ] = None,
    include_done: bool = False,
) -> str:
    """List a project's items in priority order, or the inbox (newest first) if no project_id.

    To find an item the user mentions, use search instead of listing every project.
    Titles and status only; use get_item for details and history.
    """
    ids = await run(services.short_ids)
    if search is not None:
        found = await run(services.search_items, search, include_done)
        return as_text([ItemSummary.of(i, ids, with_project=True) for i in found])
    if project_id is None:
        items = await run(services.list_inbox)
    else:
        items = await run(services.list_project_items, project_id)
        if not include_done:
            items = [i for i in items if i.status != ItemStatus.DONE]
    return as_text([ItemSummary.of(i, ids) for i in items])


@tool(read_only=True)
async def get_item(item_id: ItemId) -> str:
    """Get one item with its details and activity log."""
    item = await resolve(item_id)
    activity = await run(services.list_activity, item.id)
    return as_text(ItemOut.of(item, await run(services.short_ids), activity))


# --- Writing -----------------------------------------------------------------


@tool()
async def add_item(
    title: Annotated[str, Field(description="Short title, one line.")],
    details: Annotated[str, Field(description="Optional longer notes.")] = "",
    project_id: Annotated[UUID | None, Field(description="Omit to add to the inbox.")] = None,
) -> str:
    """Add an item. Without project_id it goes to the inbox.

    With one, it goes to the bottom of that project's list.
    """
    item = await run(services.add_item, title, details, project_id, Author.CLAUDE)
    return as_text(ItemOut.of(item, await run(services.short_ids)))


@tool(destructive=True)
async def update_item(item_id: ItemId, title: str | None = None, details: str | None = None) -> str:
    """Replace an item's title and/or details. Status changes go through set_status."""
    item = await run(services.update_item, (await resolve(item_id)).id, title, details)
    return as_text(ItemOut.of(item, await run(services.short_ids)))


@tool()
async def set_status(
    item_id: ItemId,
    status: Literal["open", "doing", "done"],
    comment: Annotated[
        str,
        Field(
            description="Why, in a sentence the user would write; include context from the "
            "conversation. Required; saved in the activity log."
        ),
    ],
) -> str:
    """Change an item's status. Inbox items must be moved to a project first."""
    ref = (await resolve(item_id)).id
    item = await run(services.set_status, ref, ItemStatus(status), comment, Author.CLAUDE)
    return as_text(ItemOut.of(item, await run(services.short_ids)))


@tool()
async def move_item(
    item_id: ItemId,
    project_id: Annotated[UUID | None, Field(description="Omit to move back to the inbox.")] = None,
) -> str:
    """Move an item to a project (to the bottom of its list), or back to the inbox.

    Only open items can go back to the inbox.
    """
    item = await run(services.move_item, (await resolve(item_id)).id, project_id, Author.CLAUDE)
    return as_text(ItemOut.of(item, await run(services.short_ids)))


@tool()
async def add_comment(item_id: ItemId, text: str) -> str:
    """Add a note to an item's activity log: progress, a decision, a finding."""
    await run(services.add_comment, (await resolve(item_id)).id, text, Author.CLAUDE)
    return "Comment added."


@tool()
async def create_project(name: str, description: str = "", repo_url: str = "") -> str:
    """Create a project. It starts as an idea; only the user changes a project's state."""
    project = await run(services.create_project, name, description, repo_url)
    return as_text(ProjectOut.of(project))


@tool(destructive=True)
async def update_project(
    project_id: ProjectId,
    name: str | None = None,
    description: str | None = None,
    repo_url: Annotated[str | None, Field(description="Empty string removes it.")] = None,
) -> str:
    """Change a project's name, description or repo link. Only the user changes its state."""
    project = await run(services.update_project, project_id, name, description, repo_url)
    return as_text(ProjectOut.of(project))


# --- Reordering, confirmed by the user where the client can ask --------------
# DECISIONS #7: clients must ask the user before every reorder. A hint can't
# guarantee that, so the server asks itself, through elicitation: the first call
# returns `input_required` with a question for the user; the client shows it and
# retries the call with the answer. No "accept", no reorder.
# DECISIONS #59: a client that can't ask (no form elicitation, or an older
# protocol revision, which a stateless server can't send a question on) gets
# the order applied unconfirmed, and the result says so.


class Confirm(BaseModel):
    """Elicitation form with no fields: accept or decline is the whole answer."""


class NotAsked(BaseModel):
    """The client can't show the question, so nobody was asked."""


def can_ask(ctx: Context[Any, Any]) -> bool:
    """Whether this request can carry a question for the user back to the client.

    Only 2026-07-28+ (`input_required`) can: older revisions need a stream for a
    server-to-client request, which a stateless server doesn't have (DECISIONS #20).
    The capability test is the SDK's own: a bare `elicitation: {}` counts as form
    support, url-only doesn't.
    """
    capabilities = ctx.client_capabilities
    elicitation = capabilities.elicitation if capabilities is not None else None
    can_form = elicitation is not None and (elicitation.form is not None or elicitation.url is None)
    return can_form and is_version_at_least(ctx.session.protocol_version, "2026-07-28")


async def confirm_order(
    ctx: Context[Any, Any], project_id: UUID, item_ids: list[str]
) -> Elicit[Confirm] | NotAsked:
    # A resolver: runs before the tool body and gets the tool's arguments by name
    # (and the request context by type). The list is checked before the user is
    # asked, so they never confirm an invalid order. The SDK pins the answer to
    # this exact message: if the list changes between rounds, the user is asked again.
    project = await run(services.get_project, project_id)
    moves = await run(services.order_moves, project_id, await run(_resolve_all, item_ids))
    if not can_ask(ctx):
        # Not a question, so the SDK hands it straight to the tool as "accepted".
        return NotAsked()
    ids = await run(services.short_ids)
    return Elicit(f"Claude wants to reorder {project.name!r}: {describe(moves, ids)}", Confirm)


def describe(moves: list[services.Move], ids: dict[UUID, str], shown: int = 3) -> str:
    """One line (claude.ai drops line breaks, Claude Code shows only the first few)."""
    if not moves:
        return "the order stays the same."
    parts = [
        f'move #{ids[m.item.id]} "{shorten(m.item.title)}" from {m.old} to {m.new}' for m in moves[:shown]
    ]
    if len(moves) > shown:
        parts.append(f"and {len(moves) - shown} more")
    return "; ".join(parts) + "."


def shorten(title: str, width: int = 40) -> str:
    return title if len(title) <= width else title[: width - 1].rstrip() + "…"


@tool(destructive=True)
async def reorder_items(
    project_id: ProjectId,
    item_ids: Annotated[list[str], Field(description="Every open and doing item's id, top first.")],
    confirmation: Annotated[ElicitationResult[Confirm | NotAsked], Resolve(confirm_order)],
) -> str:
    """Set a project's priority order. Call only when the user asked to reprioritize.

    Where the app can ask, the user confirms before anything changes; elsewhere the order is applied directly.
    """
    if not isinstance(confirmation, AcceptedElicitation):
        raise ToolError(f"The user did not confirm ({confirmation.action}). The order is unchanged.")
    items = await run(services.set_order, project_id, await run(_resolve_all, item_ids))
    ids = await run(services.short_ids)
    # Claude never sees the question or the answer (client and server handle
    # them), so the result says what happened.
    if isinstance(confirmation.data, NotAsked):
        head = "This app can't ask the user to confirm, so the order was applied unconfirmed. New order: "
    else:
        head = "The user confirmed. New order: "
    return head + as_text([ItemSummary.of(i, ids) for i in items])
