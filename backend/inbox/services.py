"""Every rule lives here. The API and the MCP tools only call these functions."""

from .models import Item


class RuleViolation(Exception):
    """A request broke a rule. The message is shown to the caller (me or Claude)."""


async def list_items() -> list[Item]:
    return [item async for item in Item.objects.all()]


async def add_item(title: str, details: str = "") -> Item:
    title = title.strip()
    if not title:
        raise RuleViolation("An item needs a title.")
    return await Item.objects.acreate(title=title, details=details.strip())
