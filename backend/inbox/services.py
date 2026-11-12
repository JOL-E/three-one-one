"""Every rule lives here. The API and the MCP tools only call these functions.

Services are sync and each write runs in one transaction: Django (6.1) has no
async `transaction.atomic`, and e.g. a status change must write the item and its
log entry together or not at all. Async callers (the MCP tools) wrap them with
`sync_to_async`.

Who may call what (DECISIONS #7) is decided by which door exposes a function:
`set_project_state`, `delete_project` and `delete_item` are never MCP tools.
"""

from collections import defaultdict
from typing import NamedTuple
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Count, Max, QuerySet
from django.utils import timezone

from .models import Activity, ActivityKind, Author, Item, ItemStatus, ItemType, Project, ProjectState


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
        return Item.objects.select_related("project", "milestone").get(pk=item_id)
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
    matches = list(Item.objects.select_related("project", "milestone").filter(id__istartswith=key)[:6])
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
# Open and Doing items in a project have positions 0..n-1 (0 = top), counted per
# level (DECISIONS #78): the project's top level (milestones and loose tasks), or
# one milestone's tasks. Inbox and Done items have none. Every change that adds
# or removes a ranked item keeps each level's sequence gapless.


def _ranked(project_id: UUID, milestone_id: UUID | None = None) -> QuerySet[Item]:
    return (
        Item.objects.filter(project_id=project_id, milestone_id=milestone_id)
        .exclude(status=ItemStatus.DONE)
        .order_by("position", "created_at")
    )


def _next_position(project_id: UUID, milestone_id: UUID | None = None) -> int:
    highest = _ranked(project_id, milestone_id).aggregate(highest=Max("position"))["highest"]
    return 0 if highest is None else highest + 1


def _write_order(item_ids: list[UUID]) -> None:
    for position, item_id in enumerate(item_ids):
        Item.objects.filter(pk=item_id).exclude(position=position).update(position=position)


def _close_gaps(project_id: UUID | None, milestone_id: UUID | None = None) -> None:
    if project_id is not None:
        _write_order(list(_ranked(project_id, milestone_id).values_list("id", flat=True)))


# --- Milestones (DECISIONS #71–80) ---------------------------------------------
# A milestone is an item of type milestone; a task joins one through
# `Item.milestone`. The rules that span rows live here only (#77): a task's
# milestone is a milestone of the same project, and a done milestone has no open
# or doing tasks, so a task can't join or reopen in one.


def _milestone_to_join(milestone_id: UUID) -> Item:
    milestone = get_item(milestone_id)
    if milestone.type != ItemType.MILESTONE:
        raise RuleViolation(f"{milestone.title!r} is not a milestone.")
    if milestone.status == ItemStatus.DONE:
        raise RuleViolation(f"The milestone {milestone.title!r} is done. Reopen it first.")
    return milestone


def _value(text: str) -> str:
    """Fits an activity's old/new value (100 characters)."""
    return text if len(text) <= 100 else text[:99] + "…"


def _where(item: Item) -> str:
    """Where an item lives, for the log: its milestone, its project or the inbox."""
    if item.milestone is not None:
        return _value(item.milestone.title)
    return item.project.name if item.project else "Inbox"


# --- Items -------------------------------------------------------------------


def list_inbox() -> list[Item]:
    return list(Item.objects.filter(project__isnull=True).order_by("-created_at"))


def list_project_items(project_id: UUID) -> list[Item]:
    """Ranked items top to bottom, each milestone followed by its ranked tasks.

    Then Done items, most recently finished first.
    """
    project = get_project(project_id)
    tasks: dict[UUID, list[Item]] = defaultdict(list)
    in_milestones = (
        project.items.filter(milestone__isnull=False)
        .exclude(status=ItemStatus.DONE)
        .order_by("position", "created_at")
    )
    for task in in_milestones:
        assert task.milestone_id is not None
        tasks[task.milestone_id].append(task)
    ranked = [i for top in _ranked(project.id) for i in [top, *tasks[top.id]]]
    done = project.items.filter(status=ItemStatus.DONE).order_by("-done_at")
    return [*ranked, *done]


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
    item_type: ItemType = ItemType.TASK,
    milestone_id: UUID | None = None,
) -> Item:
    """Without a project the item lands in the inbox; with one, at the bottom of its list.

    With a milestone it lands at the bottom of that milestone, in its project.
    The app may pass the new item's id (generated on the device), so it can show
    the item before the server answers. Claude never does.
    """
    title = _required(title, "An item needs a title.")
    if item_id is not None and Item.objects.filter(pk=item_id).exists():
        raise RuleViolation(f"An item with id {item_id} already exists.")
    item = Item(title=title, details=details.strip(), type=item_type)
    if item_id is not None:
        item.id = item_id
    if milestone_id is not None:
        if item_type == ItemType.MILESTONE:
            raise RuleViolation("A milestone can't be in another milestone.")
        item.milestone = _milestone_to_join(milestone_id)
        if project_id is not None and project_id != item.milestone.project_id:
            raise RuleViolation(f"The milestone {item.milestone.title!r} is in another project.")
        project_id = item.milestone.project_id
    if project_id is not None:
        item.project = get_project(project_id)
        item.position = _next_position(project_id, milestone_id)
    elif item_type == ItemType.MILESTONE:
        raise RuleViolation("A milestone needs a project; the inbox holds only tasks.")
    item.save()
    Activity.objects.create(item=item, author=author, kind=ActivityKind.CREATED)
    return item


@transaction.atomic
def update_item(
    item_id: UUID,
    title: str | None = None,
    details: str | None = None,
    item_type: ItemType | None = None,
    author: Author = Author.OWNER,
) -> Item:
    """Edits to title and details aren't logged (they'd drown the log); type changes are."""
    item = get_item(item_id)
    if title is not None:
        item.title = _required(title, "An item needs a title.")
    if details is not None:
        item.details = details.strip()
    old_type = ItemType(item.type)
    if item_type is not None and item_type != old_type:
        if item_type == ItemType.MILESTONE and item.project_id is None:
            raise RuleViolation("Sort the item into a project first; the inbox holds only tasks.")
        if item_type == ItemType.MILESTONE and item.milestone_id is not None:
            raise RuleViolation("Take the item out of its milestone first; a milestone can't be in another.")
        if item_type == ItemType.TASK and (n := item.tasks.count()):
            raise RuleViolation(f"Move this milestone's {n} task(s) out first.")
        item.type = item_type
        Activity.objects.create(
            item=item,
            author=author,
            kind=ActivityKind.TYPE,
            old_value=old_type.label,
            new_value=item_type.label,
        )
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
    if status == ItemStatus.DONE and item.type == ItemType.MILESTONE:
        if n := item.tasks.exclude(status=ItemStatus.DONE).count():
            raise RuleViolation(
                f"The milestone still has {n} open or doing task(s). Finish or move them first."
            )
    if old == ItemStatus.DONE and item.milestone is not None and item.milestone.status == ItemStatus.DONE:
        raise RuleViolation(f"The milestone {item.milestone.title!r} is done. Reopen it first.")

    if status == ItemStatus.DONE:
        item.position = None
        item.done_at = timezone.now()
    elif old == ItemStatus.DONE:
        # Reopened: back into the order, at the bottom of its level.
        item.position = _next_position(item.project_id, item.milestone_id)
        item.done_at = None
    item.status = status
    item.save()
    _close_gaps(item.project_id, item.milestone_id)
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
def move_item(
    item_id: UUID, project_id: UUID | None, author: Author, milestone_id: UUID | None = None
) -> Item:
    """Sort an inbox item into a project, or move it to another one (or back to the inbox).

    With a milestone, a task joins it (and its project) at the bottom. Moving to
    the item's own project takes it out of its milestone (DECISIONS #78). A
    milestone takes all its tasks along to another project (#74). Not a status
    change, so no comment needed; it's logged anyway.
    """
    item = get_item(item_id)
    old_project, old_milestone_id, old_where = item.project, item.milestone_id, _where(item)
    milestone = None
    if milestone_id is not None:
        if item.type == ItemType.MILESTONE:
            raise RuleViolation("A milestone can't be in another milestone.")
        if item.milestone_id == milestone_id:
            raise RuleViolation("The item is already there.")
        milestone = _milestone_to_join(milestone_id)
        if project_id is not None and project_id != milestone.project_id:
            raise RuleViolation(f"The milestone {milestone.title!r} is in another project.")
        new_project = milestone.project
    else:
        if item.project_id == project_id and item.milestone_id is None:
            raise RuleViolation("The item is already there.")
        new_project = get_project(project_id) if project_id is not None else None
        if new_project is None and item.status != ItemStatus.OPEN:
            raise RuleViolation("Only open items can go back to the inbox.")
        if new_project is None and item.type == ItemType.MILESTONE:
            raise RuleViolation("A milestone can't go to the inbox; it holds only tasks.")

    item.project, item.milestone = new_project, milestone
    ranked = new_project is not None and item.status != ItemStatus.DONE
    item.position = (
        _next_position(new_project.id, milestone_id) if new_project is not None and ranked else None
    )
    item.save()
    _close_gaps(old_project.id if old_project else None, old_milestone_id)
    Activity.objects.create(
        item=item, author=author, kind=ActivityKind.MOVED, old_value=old_where, new_value=_where(item)
    )
    if item.type == ItemType.MILESTONE and old_project != new_project:
        assert old_project is not None and new_project is not None  # milestones never sit in the inbox
        tasks = list(item.tasks.all())
        item.tasks.update(project=new_project, updated_at=timezone.now())
        Activity.objects.bulk_create(
            Activity(
                item=task,
                author=author,
                kind=ActivityKind.MOVED,
                old_value=old_project.name,
                new_value=new_project.name,
            )
            for task in tasks
        )
    return item


@transaction.atomic
def reorder_item(item_id: UUID, position: int) -> Item:
    """Move a ranked item to `position` (0 = top) within its level; others shift."""
    item = get_item(item_id)
    if item.project_id is None or item.status == ItemStatus.DONE:
        raise RuleViolation("Only open or doing items in a project have a priority order.")
    ranked = _ranked(item.project_id, item.milestone_id).values_list("id", flat=True)
    order = [i for i in ranked if i != item.id]
    order.insert(max(0, min(position, len(order))), item.id)
    _write_order(order)
    item.refresh_from_db()
    return item


def check_order(project_id: UUID, item_ids: list[UUID], milestone_id: UUID | None = None) -> list[Item]:
    """A full new order must name every open and doing item of the level exactly once.

    The level is the project's top level, or one milestone's tasks (DECISIONS #78).
    So nothing is dropped or invented by accident. Returns the items in the new order.
    """
    project = get_project(project_id)
    where = repr(project.name)
    if milestone_id is not None:
        milestone = get_item(milestone_id)
        if milestone.type != ItemType.MILESTONE or milestone.project_id != project.id:
            raise RuleViolation(f"{milestone.title!r} is not a milestone in {project.name!r}.")
        where = f"the milestone {milestone.title!r}"
    ranked = {i.id: i for i in _ranked(project.id, milestone_id)}
    if len(item_ids) != len(set(item_ids)) or set(item_ids) != set(ranked):
        raise RuleViolation(f"Pass every open and doing item of {where} exactly once ({len(ranked)} items).")
    return [ranked[i] for i in item_ids]


class Move(NamedTuple):
    item: Item
    old: int  # 1-based position before
    new: int  # and after


def order_moves(project_id: UUID, item_ids: list[UUID], milestone_id: UUID | None = None) -> list[Move]:
    """The fewest moves that turn the current order into the new one, top first.

    The largest group of items that keep their order relative to each other (a
    longest increasing subsequence) stays put; every other item counts as moved.
    So one item dragged from 3 to 6 is one move, not four shifted positions.
    Checks the new order like `check_order`.
    """
    items = check_order(project_id, item_ids, milestone_id)
    was = {item.id: n for n, item in enumerate(_ranked(project_id, milestone_id))}
    seq = [was[item.id] for item in items]
    # longest[k]: the longest increasing run ending at k; before[k]: its previous element.
    # Quadratic, which is fine for a project's few dozen items.
    longest, before = [1] * len(seq), [-1] * len(seq)
    for k in range(len(seq)):
        for j in range(k):
            if seq[j] < seq[k] and longest[j] + 1 > longest[k]:
                longest[k], before[k] = longest[j] + 1, j
    stay = set()
    k = max(range(len(seq)), key=longest.__getitem__, default=-1)
    while k != -1:
        stay.add(k)
        k = before[k]
    return [Move(item, was[item.id] + 1, n + 1) for n, item in enumerate(items) if n not in stay]


@transaction.atomic
def set_order(project_id: UUID, item_ids: list[UUID], milestone_id: UUID | None = None) -> list[Item]:
    """Replace one level's whole priority order in one go (top first)."""
    check_order(project_id, item_ids, milestone_id)
    _write_order(item_ids)
    return list(_ranked(project_id, milestone_id))


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
    """Owner only. Its activity goes with it.

    A milestone's tasks stay and lose the link; open ones go to the bottom of the
    top level (DECISIONS #79).
    """
    item = get_item(item_id)
    project_id, milestone_id = item.project_id, item.milestone_id
    if item.type == ItemType.MILESTONE:
        assert project_id is not None  # milestones never sit in the inbox
        for task in item.tasks.order_by("position", "created_at"):
            task.milestone = None
            task.position = _next_position(project_id) if task.status != ItemStatus.DONE else None
            task.save()
            Activity.objects.create(
                item=task,
                author=Author.OWNER,
                kind=ActivityKind.MOVED,
                old_value=_value(item.title),
                new_value=_where(task),
            )
    item.delete()
    _close_gaps(project_id, milestone_id)
