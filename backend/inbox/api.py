"""The app's API at /api/: the owner's door (ARCHITECTURE.md).

Thin like the MCP tools: parse, call one service, return. Every endpoint needs a
logged-in session, and writes need the CSRF header (DECISIONS #36); Ninja's
`django_auth` runs Django's own CSRF check. Until M5 builds a login screen, log
in at /admin/.

Unlike Claude, the owner may delete, change a project's state and reorder
without being asked (DECISIONS #7). URLs use full UUIDs; `short_id` is for display.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from django.http import HttpRequest
from django.middleware.csrf import get_token
from ninja import Router, Schema, Status

from . import services
from .models import Activity, Author, Item, ItemStatus, ItemType, Project, ProjectState

router = Router(tags=["inbox"])
ME = Author.OWNER


# --- Schemas -------------------------------------------------------------------


class ProjectOut(Schema):
    id: UUID
    name: str
    description: str
    repo_url: str
    state: Literal["idea", "building", "live", "archived"]
    is_general: bool
    open_items: int  # open + doing, for the sidebar


class ItemOut(Schema):
    id: UUID
    short_id: str
    project_id: UUID | None
    type: Literal["task", "milestone"]
    milestone_id: UUID | None  # the milestone a task belongs to (DECISIONS #71)
    title: str
    details: str
    status: Literal["open", "doing", "done"]
    created_by: Literal["owner", "claude"]
    position: int | None
    created_at: datetime
    updated_at: datetime
    done_at: datetime | None


class ActivityOut(Schema):
    id: UUID
    author: Literal["owner", "claude"]
    kind: Literal["created", "comment", "status", "moved", "type"]
    text: str
    old_value: str
    new_value: str
    created_at: datetime


class ItemDetail(ItemOut):
    activity: list[ActivityOut]  # oldest first


class SearchHit(ItemOut):
    project_name: str | None


class ProjectIn(Schema):
    name: str
    description: str = ""
    repo_url: str = ""


class ProjectPatch(Schema):
    name: str | None = None
    description: str | None = None
    repo_url: str | None = None


class StateIn(Schema):
    state: Literal["idea", "building", "live", "archived"]


class OrderIn(Schema):
    item_ids: list[UUID]  # every open and doing item of the level, top first
    milestone_id: UUID | None = None  # null = the project's top level (DECISIONS #78)


class ItemIn(Schema):
    title: str
    details: str = ""
    project_id: UUID | None = None
    type: Literal["task", "milestone"] = "task"
    milestone_id: UUID | None = None  # joins this milestone, in its project
    id: UUID | None = None  # generated on the device, so the item shows before the answer


class ItemPatch(Schema):
    title: str | None = None
    details: str | None = None
    type: Literal["task", "milestone"] | None = None


class StatusIn(Schema):
    status: Literal["open", "doing", "done"]
    comment: str


class MoveIn(Schema):
    project_id: UUID | None  # null = back to the inbox; the item's own project = out of its milestone
    milestone_id: UUID | None = None  # joins this milestone, in its project


class CommentIn(Schema):
    text: str


class Me(Schema):
    username: str


# --- Converting ------------------------------------------------------------------


# model_validate checks each value against the schema (e.g. a status is one of
# the Literal's values), so a model change that breaks the API fails loudly.


def project_out(p: Project, counts: dict[UUID, int]) -> ProjectOut:
    fields = {"open_items": counts.get(p.id, 0)}
    for name in ["id", "name", "description", "repo_url", "state", "is_general"]:
        fields[name] = getattr(p, name)
    return ProjectOut.model_validate(fields)


def item_fields(i: Item, ids: dict[UUID, str], creators: dict[UUID, str]) -> dict[str, object]:
    return {
        "id": i.id,
        "short_id": ids[i.id],
        "created_by": creators.get(i.id, Author.OWNER),
        "project_id": i.project_id,
        "type": i.type,
        "milestone_id": i.milestone_id,
        "title": i.title,
        "details": i.details,
        "status": i.status,
        "position": i.position,
        "created_at": i.created_at,
        "updated_at": i.updated_at,
        "done_at": i.done_at,
    }


def item_out(i: Item) -> ItemOut:
    return items_out([i])[0]


def items_out(items: list[Item]) -> list[ItemOut]:
    ids, creators = services.short_ids(), services.creators([i.id for i in items])
    return [ItemOut.model_validate(item_fields(i, ids, creators)) for i in items]


def activity_out(a: Activity) -> ActivityOut:
    return ActivityOut.model_validate(a, from_attributes=True)


# --- Session ---------------------------------------------------------------------


@router.get("/auth/csrf", auth=None, response={204: None})
def csrf(request: HttpRequest) -> Status[None]:
    """Sets the CSRF cookie; the app sends it back as `X-CSRFToken` on writes."""
    get_token(request)
    return Status(204, None)


@router.get("/me", response=Me)
def me(request: HttpRequest) -> Me:
    """Who is logged in. A 401 here means: show the login."""
    return Me(username=request.user.get_username())


# --- Projects --------------------------------------------------------------------


@router.get("/projects", response=list[ProjectOut])
def list_projects(request: HttpRequest, include_archived: bool = False) -> list[ProjectOut]:
    counts = services.open_item_counts()
    return [project_out(p, counts) for p in services.list_projects(include_archived)]


@router.post("/projects", response={201: ProjectOut})
def create_project(request: HttpRequest, data: ProjectIn) -> Status[ProjectOut]:
    project = services.create_project(data.name, data.description, data.repo_url)
    return Status(201, project_out(project, {}))


@router.patch("/projects/{project_id}", response=ProjectOut)
def update_project(request: HttpRequest, project_id: UUID, data: ProjectPatch) -> ProjectOut:
    project = services.update_project(project_id, data.name, data.description, data.repo_url)
    return project_out(project, services.open_item_counts())


@router.put("/projects/{project_id}/state", response=ProjectOut)
def set_project_state(request: HttpRequest, project_id: UUID, data: StateIn) -> ProjectOut:
    project = services.set_project_state(project_id, ProjectState(data.state))
    return project_out(project, services.open_item_counts())


@router.delete("/projects/{project_id}", response={204: None})
def delete_project(request: HttpRequest, project_id: UUID) -> Status[None]:
    services.delete_project(project_id)
    return Status(204, None)


@router.get("/projects/{project_id}/items", response=list[ItemOut])
def project_items(request: HttpRequest, project_id: UUID) -> list[ItemOut]:
    """Open and doing items top to bottom, each milestone followed by its tasks; then done, newest first."""
    return items_out(services.list_project_items(project_id))


@router.put("/projects/{project_id}/order", response=list[ItemOut])
def set_order(request: HttpRequest, project_id: UUID, data: OrderIn) -> list[ItemOut]:
    return items_out(services.set_order(project_id, data.item_ids, data.milestone_id))


# --- Items -----------------------------------------------------------------------


@router.get("/inbox", response=list[ItemOut])
def inbox(request: HttpRequest) -> list[ItemOut]:
    return items_out(services.list_inbox())


@router.get("/items/search", response=list[SearchHit])
def search(request: HttpRequest, q: str, include_done: bool = False) -> list[SearchHit]:
    found = services.search_items(q, include_done)
    ids, creators = services.short_ids(), services.creators([i.id for i in found])
    return [
        SearchHit.model_validate(
            {**item_fields(i, ids, creators), "project_name": i.project and i.project.name}
        )
        for i in found
    ]


@router.post("/items", response={201: ItemOut})
def add_item(request: HttpRequest, data: ItemIn) -> Status[ItemOut]:
    item = services.add_item(
        data.title,
        data.details,
        data.project_id,
        ME,
        item_id=data.id,
        item_type=ItemType(data.type),
        milestone_id=data.milestone_id,
    )
    return Status(201, item_out(item))


@router.get("/items/{item_id}", response=ItemDetail)
def get_item(request: HttpRequest, item_id: UUID) -> ItemDetail:
    item = services.get_item(item_id)
    activity = [activity_out(a) for a in services.list_activity(item_id)]
    fields = item_fields(item, services.short_ids(), services.creators([item.id]))
    return ItemDetail.model_validate({**fields, "activity": activity})


@router.patch("/items/{item_id}", response=ItemOut)
def update_item(request: HttpRequest, item_id: UUID, data: ItemPatch) -> ItemOut:
    item_type = ItemType(data.type) if data.type is not None else None
    return item_out(services.update_item(item_id, data.title, data.details, item_type, ME))


@router.post("/items/{item_id}/status", response=ItemOut)
def set_status(request: HttpRequest, item_id: UUID, data: StatusIn) -> ItemOut:
    return item_out(services.set_status(item_id, ItemStatus(data.status), data.comment, ME))


@router.post("/items/{item_id}/move", response=ItemOut)
def move_item(request: HttpRequest, item_id: UUID, data: MoveIn) -> ItemOut:
    return item_out(services.move_item(item_id, data.project_id, ME, data.milestone_id))


@router.post("/items/{item_id}/comments", response={201: ActivityOut})
def add_comment(request: HttpRequest, item_id: UUID, data: CommentIn) -> Status[ActivityOut]:
    return Status(201, activity_out(services.add_comment(item_id, data.text, ME)))


@router.delete("/items/{item_id}", response={204: None})
def delete_item(request: HttpRequest, item_id: UUID) -> Status[None]:
    services.delete_item(item_id)
    return Status(204, None)
