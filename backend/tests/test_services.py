import pytest

from inbox import services

pytestmark = pytest.mark.django_db(transaction=True)


async def test_add_item_strips_whitespace() -> None:
    item = await services.add_item("  Try a new e-ink panel  ", "  notes ")
    assert item.title == "Try a new e-ink panel"
    assert item.details == "notes"


async def test_add_item_rejects_empty_title() -> None:
    with pytest.raises(services.RuleViolation):
        await services.add_item("   ")


async def test_list_items_newest_first() -> None:
    await services.add_item("first")
    await services.add_item("second")
    assert [i.title for i in await services.list_items()] == ["second", "first"]
