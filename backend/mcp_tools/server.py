"""The MCP server: which tools Claude sees, and how they map to the services.

The SDK builds each tool's JSON Schema (`inputSchema` in `tools/list`) from the
function's type hints, and its description from the docstring. Tools stay thin:
they translate between MCP and the services layer, nothing more.
"""

from datetime import datetime
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field

from inbox import services
from inbox.models import Item

server = MCPServer(
    name="311",
    version="0.1.0",
    instructions="An inbox for side-project ideas. Use it to capture ideas the user mentions.",
)


class ItemOut(BaseModel):
    id: str
    title: str
    details: str
    created_at: datetime

    @classmethod
    def from_item(cls, item: Item) -> ItemOut:
        return cls(id=str(item.id), title=item.title, details=item.details, created_at=item.created_at)


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
async def list_items() -> list[ItemOut]:
    """List every item in the inbox, newest first."""
    return [ItemOut.from_item(item) for item in await services.list_items()]


@server.tool()
async def add_item(
    title: Annotated[str, Field(description="Short title, one line.")],
    details: Annotated[str, Field(description="Optional longer notes.")] = "",
) -> ItemOut:
    """Add an idea to the inbox."""
    try:
        item = await services.add_item(title, details)
    except services.RuleViolation as exc:
        # ToolError's message reaches Claude as an `isError: true` result.
        raise ToolError(str(exc)) from exc
    return ItemOut.from_item(item)
