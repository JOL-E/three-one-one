"""Every rule lives here. The API and the MCP tools only call these functions.

Services are sync and each write runs in one transaction: Django (6.1) has no
async `transaction.atomic`, and e.g. a status change must write the item and its
log entry together or not at all. Async callers (the MCP tools) wrap them with
`sync_to_async`.

Who may call what (DECISIONS #7) is decided by which door exposes a function:
`set_project_state`, `delete_project` and `delete_item` are never MCP tools.
"""

from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Count, Max, QuerySet
from django.utils import timezone

from .models import Activity, ActivityKind, Author, Item, ItemStatus, Project, ProjectState


class RuleViolation(Exception):
    """A request broke a rule. The message is shown to the caller (me or Claude)."""


class NotFound(RuleViolation):
    """The project or item doesn't exist. The API answers 404 instead of 400."""


def _required(text: str, message: str) -> str:
    text = text.strip()
    if not text:
        raise RuleViolation(message)
    return text


# --- Lookups -----------------------------------------------------------------


def get_project(project_id: UUID) -> Project:
    try:
        return Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        raise NotFound(f"There is no project with id {project_id}.") from None


def get_item(item_id: UUID) -> Item:
    try:
        return Item.objects.select_related("project").get(pk=item_id)
    except Item.DoesNotExist:
        raise NotFound(f"There is no item with id {item_id}.") from None


# --- Short item IDs (DECISIONS #40) -------------------------------------------
# The shortest start of an item's UUID that no other item shares, at least 4 hex
# characters, upper case: "3F9A". Computed on demand, never stored. An item's
# short ID can grow when a new item shares its start; old references then
# become ambiguous and are refused, naming the candidates (like git).

SHORT_ID_MIN = 4


def short_ids() -> dict[UUID, str]:
    """Every item's short ID. Uniqueness is among all items, not just the ones shown."""
    hexes = sorted(i.hex for i in Item.objects.values_list("id", flat=True))

    def shared(a: str, b: str) -> int:
        n = 0
        while n < len(a) and a[n] == b[n]:
            n += 1
        return n

    result: dict[UUID, str] = {}
    for n, h in enumerate(hexes):
        before = shared(h, hexes[n - 1]) if n > 0 else 0
        after = shared(h, hexes[n + 1]) if n + 1 < len(hexes) else 0
        result[UUID(h)] = h[: max(SHORT_ID_MIN, before + 1, after + 1)].upper()
    return result


def resolve_item(ref: str) -> Item:
    """Find an item by its full UUID or any unique start of it ("3F9A", "#3f9a7")."""
    key = ref.strip().lstrip("#").replace("-", "").lower()
    if len(key) < SHORT_ID_MIN or any(c not in "0123456789abcdef" for c in key):
        raise RuleViolation(f"{ref!r} is not an item id (at least {SHORT_ID_MIN} hex characters).")
    if len(key) == 32:
        return get_item(UUID(key))
    matches = list(Item.objects.select_related("project").filter(id__istartswith=key)[:6])
    if not matches:
        raise NotFound(f"There is no item with id {ref}.")
    if len(matches) > 1:
        ids = short_ids()
        names = ", ".join(f"{ids[i.id]} ({i.title})" for i in matches[:5])
        raise RuleViolation(f"{ref} matches several items: {names}. Use more characters.")
    return matches[0]


def general_project() -> Project:
    return Project.objects.get(is_general=True)


# --- Projects ----------------------------------------------------------------


def list_projects(include_archived: bool = False) -> list[Project]:
    projects = Project.objects.all()
    if not include_archived:
        projects = projects.exclude(state=ProjectState.ARCHIVED)
    return list(projects)


def open_item_counts() -> dict[UUID, int]:
    """Open and doing items per project (the sidebar's numbers)."""
    rows = (
        Item.objects.filter(project__isnull=False)
        .exclude(status=ItemStatus.DONE)
        .values("project")
        .annotate(n=Count("id"))
    )
    return {row["project"]: row["n"] for row in rows}


def _unique_name(name: str, exclude: UUID | None = None) -> str:
    name = _required(name, "A project needs a name.")
    others = Project.objects.filter(name__iexact=name)
    if exclude is not None:
        others = others.exclude(pk=exclude)
    if others.exists():
        raise RuleViolation(f"A project named {name!r} already exists.")
    return name


def _repo_url(repo_url: str) -> str:
    repo_url = repo_url.strip()
    if repo_url:
        try:
            URLValidator(schemes=["http", "https"])(repo_url)
        except ValidationError:
            raise RuleViolation(f"{repo_url!r} is not a valid http(s) URL.") from None
    return repo_url


def create_project(name: str, description: str = "", repo_url: str = "") -> Project:
    """New projects always start as Idea; only the owner moves them on (DECISIONS #7)."""
    return Project.objects.create(
        name=_unique_name(name), description=description.strip(), repo_url=_repo_url(repo_url)
    )


def update_project(
    project_id: UUID, name: str | None = None, description: str | None = None, repo_url: str | None = None
) -> Project:
    """Name, description and repo link; me or Claude (DECISIONS #37). State is separate.

    General keeps its name: the MCP instructions refer to it by name.
    """
    project = get_project(project_id)
    if name is not None:
        name = _unique_name(name, exclude=project.id)
        if project.is_general and name != project.name:
            raise RuleViolation("The General project keeps its name.")
        project.name = name
    if description is not None:
        project.description = description.strip()
    if repo_url is not None:
        project.repo_url = _repo_url(repo_url)
    project.save()
    return project


def set_project_state(project_id: UUID, state: ProjectState) -> Project:
    """Any state to any other (DECISIONS #3 is not strictly linear). Owner only."""
    project = get_project(project_id)
    if project.is_general:
        raise RuleViolation("The General project is permanent; its state can't change.")
    project.state = state
    project.save(update_fields=["state", "updated_at"])
    return project


def delete_project(project_id: UUID) -> None:
    """Owner only. Archiving is the normal end; deleting is for mistakes."""
    project = get_project(project_id)
    if project.is_general:
        raise RuleViolation("The General project is permanent and can't be deleted.")
    if project.items.exists():
        raise RuleViolation("Move or delete the project's items first.")
    project.delete()


# --- Priority order ----------------------------------------------------------
# Open and Doing items in a project have positions 0..n-1 (0 = top). Inbox and
# Done items have none. Every change that adds or removes a ranked item keeps
# the sequence gapless.


def _ranked(project_id: UUID) -> QuerySet[Item]:
    return (
        Item.objects.filter(project_id=project_id)
        .exclude(status=ItemStatus.DONE)
        .order_by("position", "created_at")
    )


def _next_position(project_id: UUID) -> int:
    highest = _ranked(project_id).aggregate(highest=Max("position"))["highest"]
    return 0 if highest is None else highest + 1


def _write_order(item_ids: list[UUID]) -> None:
    for position, item_id in enumerate(item_ids):
        Item.objects.filter(pk=item_id).exclude(position=position).update(position=position)


def _close_gaps(project_id: UUID | None) -> None:
    if project_id is not None:
        _write_order(list(_ranked(project_id).values_list("id", flat=True)))


# --- Items -------------------------------------------------------------------


def list_inbox() -> list[Item]:
    return list(Item.objects.filter(project__isnull=True).order_by("-created_at"))


def list_project_items(project_id: UUID) -> list[Item]:
    """Ranked items top to bottom, then Done items, most recently finished first."""
    project = get_project(project_id)
    done = project.items.filter(status=ItemStatus.DONE).order_by("-done_at")
    return [*_ranked(project.id), *done]


SEARCH_ID_MIN = 2


def search_items(query: str, include_done: bool = False) -> list[Item]:
    """Items in the inbox and every project whose title contains all the words, newest first.

    A single word that could start a short ID ("6A", "#6a62") also finds the items
    whose ID starts with it. Those come first.
    """
    words = query.split()
    if not words:
        raise RuleViolation("Search needs at least one word.")
    items = Item.objects.select_related("project").order_by("-created_at")
    if not include_done:
        items = items.exclude(status=ItemStatus.DONE)
    by_id: list[Item] = []
    key = words[0].lstrip("#").lower()
    if len(words) == 1 and len(key) >= SEARCH_ID_MIN and all(c in "0123456789abcdef" for c in key):
        by_id = list(items.filter(id__istartswith=key))
    by_title = items
    for word in words:
        by_title = by_title.filter(title__icontains=word)
    seen = {i.id for i in by_id}
    return [*by_id, *(i for i in by_title if i.id not in seen)]


@transaction.atomic
def add_item(
    title: str,
    details: str = "",
    project_id: UUID | None = None,
    author: Author = Author.OWNER,
    item_id: UUID | None = None,
) -> Item:
    """Without a project the item lands in the inbox; with one, at the bottom of its list.

    The app may pass the new item's id (generated on the device), so it can show
    the item before the server answers. Claude never does.
    """
    title = _required(title, "An item needs a title.")
    if item_id is not None and Item.objects.filter(pk=item_id).exists():
        raise RuleViolation(f"An item with id {item_id} already exists.")
    item = Item(title=title, details=details.strip())
    if item_id is not None:
        item.id = item_id
    if project_id is not None:
        item.project = get_project(project_id)
        item.position = _next_position(project_id)
    item.save()
    Activity.objects.create(item=item, author=author, kind=ActivityKind.CREATED)
    return item


def update_item(item_id: UUID, title: str | None = None, details: str | None = None) -> Item:
    """Edits to title and details aren't logged (they'd drown the log)."""
    item = get_item(item_id)
    if title is not None:
        item.title = _required(title, "An item needs a title.")
    if details is not None:
        item.details = details.strip()
    item.save()
    return item


@transaction.atomic
def set_status(item_id: UUID, status: ItemStatus, comment: str, author: Author) -> Item:
    """DECISIONS #5: every status change comes with a comment saying why."""
    comment = _required(comment, "A status change needs a comment saying why.")
    item = get_item(item_id)
    if item.project_id is None:
        raise RuleViolation("Sort the item into a project before changing its status.")
    old = ItemStatus(item.status)
    if old == status:
        raise RuleViolation(f"The item is already {old.label}.")

    if status == ItemStatus.DONE:
        item.position = None
        item.done_at = timezone.now()
    elif old == ItemStatus.DONE:
        # Reopened: back into the order, at the bottom.
        item.position = _next_position(item.project_id)
        item.done_at = None
    item.status = status
    item.save()
    _close_gaps(item.project_id)
    Activity.objects.create(
        item=item,
        author=author,
        kind=ActivityKind.STATUS,
        text=comment,
        old_value=old.label,
        new_value=status.label,
    )
    return item


@transaction.atomic
def move_item(item_id: UUID, project_id: UUID | None, author: Author) -> Item:
    """Sort an inbox item into a project, or move it to another one (or back to the inbox).

    Not a status change, so no comment needed; it's logged anyway.
    """
    item = get_item(item_id)
    if item.project_id == project_id:
        raise RuleViolation("The item is already there.")
    old_project = item.project
    new_project = get_project(project_id) if project_id is not None else None
    if new_project is None and item.status != ItemStatus.OPEN:
        raise RuleViolation("Only open items can go back to the inbox.")

    item.project = new_project
    ranked = new_project is not None and item.status != ItemStatus.DONE
    item.position = _next_position(new_project.id) if new_project is not None and ranked else None
    item.save()
    _close_gaps(old_project.id if old_project else None)
    Activity.objects.create(
        item=item,
        author=author,
        kind=ActivityKind.MOVED,
        old_value=old_project.name if old_project else "Inbox",
        new_value=new_project.name if new_project else "Inbox",
    )
    return item


@transaction.atomic
def reorder_item(item_id: UUID, position: int) -> Item:
    """Move a ranked item to `position` (0 = top) within its project; others shift."""
    item = get_item(item_id)
    if item.project_id is None or item.status == ItemStatus.DONE:
        raise RuleViolation("Only open or doing items in a project have a priority order.")
    order = [i for i in _ranked(item.project_id).values_list("id", flat=True) if i != item.id]
    order.insert(max(0, min(position, len(order))), item.id)
    _write_order(order)
    item.refresh_from_db()
    return item


def check_order(project_id: UUID, item_ids: list[UUID]) -> list[Item]:
    """A full new order must name every open and doing item exactly once.

    So nothing is dropped or invented by accident. Returns the items in the new order.
    """
    project = get_project(project_id)
    ranked = {i.id: i for i in _ranked(project.id)}
    if len(item_ids) != len(set(item_ids)) or set(item_ids) != set(ranked):
        raise RuleViolation(
            f"Pass every open and doing item of {project.name!r} exactly once ({len(ranked)} items)."
        )
    return [ranked[i] for i in item_ids]


@transaction.atomic
def set_order(project_id: UUID, item_ids: list[UUID]) -> list[Item]:
    """Replace a project's whole priority order in one go (top first)."""
    check_order(project_id, item_ids)
    _write_order(item_ids)
    return list(_ranked(project_id))


def add_comment(item_id: UUID, text: str, author: Author) -> Activity:
    text = _required(text, "A comment can't be empty.")
    return Activity.objects.create(
        item=get_item(item_id), author=author, kind=ActivityKind.COMMENT, text=text
    )


def creators(item_ids: list[UUID]) -> dict[UUID, str]:
    """Who created each item ("owner" or "claude"), from its first log entry."""
    rows = Activity.objects.filter(kind=ActivityKind.CREATED, item_id__in=item_ids)
    return dict(rows.values_list("item_id", "author"))


def list_activity(item_id: UUID) -> list[Activity]:
    return list(get_item(item_id).activities.all())


@transaction.atomic
def delete_item(item_id: UUID) -> None:
    """Owner only. Its activity goes with it."""
    item = get_item(item_id)
    project_id = item.project_id
    item.delete()
    _close_gaps(project_id)
