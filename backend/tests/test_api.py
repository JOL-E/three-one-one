"""The owner's door: session + CSRF, and each endpoint reaching its service."""

import uuid
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test import Client

from inbox import services
from inbox.models import Author, ItemStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner() -> User:
    return User.objects.create_user("owner", password="synthetic-pass", is_staff=True)


@pytest.fixture
def api(owner: User) -> Client:
    """Logged in, with CSRF enforced like a browser."""
    c = Client(enforce_csrf_checks=True)
    c.force_login(owner)
    c.get("/api/auth/csrf")
    c.defaults["HTTP_X_CSRFTOKEN"] = c.cookies["csrftoken"].value
    return c


def body(response: Any) -> Any:
    return response.json()


def send(c: Client, method: str, url: str, data: object, **extra: Any) -> Any:
    """A JSON request, as the app sends it."""
    return getattr(c, method)(url, data, content_type="application/json", **extra)


# --- Session and CSRF (DECISIONS #36) -------------------------------------------


def test_everything_needs_a_session() -> None:
    c = Client()
    assert c.get("/api/inbox").status_code == 401
    assert send(c, "post", "/api/items", {"title": "x"}).status_code == 401
    assert c.get("/api/health").status_code == 200  # the only open endpoint, besides auth/csrf


def test_writes_need_the_csrf_header(owner: User) -> None:
    c = Client(enforce_csrf_checks=True)
    c.force_login(owner)
    c.get("/api/auth/csrf")
    assert send(c, "post", "/api/items", {"title": "x"}).status_code == 403
    token = c.cookies["csrftoken"].value
    response = send(c, "post", "/api/items", {"title": "x"}, HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 201


def test_me_names_the_user(api: Client) -> None:
    assert body(api.get("/api/me")) == {"username": "owner"}


def test_docs_are_for_staff_only(api: Client) -> None:
    assert Client().get("/api/docs").status_code == 302  # to the admin login
    assert api.get("/api/docs").status_code == 200


# --- Items ---------------------------------------------------------------------


def test_capture_sort_and_finish_an_item(api: Client) -> None:
    item_id = uuid.uuid4()
    created = send(api, "post", "/api/items", {"title": "Synthetic idea", "id": str(item_id)})
    assert created.status_code == 201
    assert body(created)["id"] == str(item_id)  # the id made on the device is kept
    assert body(created)["short_id"] == item_id.hex[:4].upper()
    assert body(created)["created_by"] == "owner"
    assert [i["title"] for i in body(api.get("/api/inbox"))] == ["Synthetic idea"]

    project = body(send(api, "post", "/api/projects", {"name": "Synthetic"}))
    send(api, "post", f"/api/items/{item_id}/move", {"project_id": project["id"]})
    done = send(api, "post", f"/api/items/{item_id}/status", {"status": "done", "comment": "Shipped"})
    assert body(done)["status"] == "done"

    detail = body(api.get(f"/api/items/{item_id}"))
    assert [(a["kind"], a["author"]) for a in detail["activity"]] == [
        ("created", "owner"),
        ("moved", "owner"),
        ("status", "owner"),
    ]


def test_broken_rule_comes_back_as_400_with_its_message(api: Client) -> None:
    project = services.create_project("Synthetic")
    item = services.add_item("x", project_id=project.id)
    response = send(api, "post", f"/api/items/{item.id}/status", {"status": "doing", "comment": " "})
    assert response.status_code == 400
    assert body(response) == {"detail": "A status change needs a comment saying why."}


def test_unknown_item_is_404(api: Client) -> None:
    response = api.get(f"/api/items/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "no item" in body(response)["detail"]


def test_edit_comment_and_delete_an_item(api: Client) -> None:
    item = services.add_item("Old title")
    edited = send(api, "patch", f"/api/items/{item.id}", {"title": "New title"})
    assert body(edited)["title"] == "New title"
    comment = send(api, "post", f"/api/items/{item.id}/comments", {"text": "A note"})
    assert (comment.status_code, body(comment)["author"]) == (201, "owner")
    assert api.delete(f"/api/items/{item.id}").status_code == 204
    assert body(api.get("/api/inbox")) == []


def test_search_names_the_project(api: Client) -> None:
    project = services.create_project("Synthetic")
    services.add_item("Lint Dockerfiles", project_id=project.id)
    services.add_item("Dockerfile notes")
    hits = body(api.get("/api/items/search", {"q": "dockerfile"}))
    assert [(h["title"], h["project_name"]) for h in hits] == [
        ("Dockerfile notes", None),
        ("Lint Dockerfiles", "Synthetic"),
    ]


# --- Projects ------------------------------------------------------------------


def test_projects_list_counts_open_items(api: Client) -> None:
    project = services.create_project("Synthetic")
    services.add_item("a", project_id=project.id)
    done = services.add_item("b", project_id=project.id)
    services.set_status(done.id, ItemStatus.DONE, "Finished", Author.OWNER)
    counts = {p["name"]: p["open_items"] for p in body(api.get("/api/projects"))}
    assert counts == {"General": 0, "Synthetic": 1}


def test_owner_reorders_without_being_asked(api: Client) -> None:
    project = services.create_project("Synthetic")
    a, b = (services.add_item(t, project_id=project.id) for t in "ab")
    response = send(api, "put", f"/api/projects/{project.id}/order", {"item_ids": [str(b.id), str(a.id)]})
    assert [i["title"] for i in body(response)] == ["b", "a"]


def test_owner_edits_project_and_changes_its_state(api: Client) -> None:
    project = services.create_project("Synthetic")
    url = f"/api/projects/{project.id}"
    assert body(send(api, "patch", url, {"description": "Notes"}))["description"] == "Notes"
    assert body(send(api, "put", f"{url}/state", {"state": "live"}))["state"] == "live"
    general = services.general_project()
    response = send(api, "put", f"/api/projects/{general.id}/state", {"state": "archived"})
    assert response.status_code == 400


def test_project_with_items_cannot_be_deleted(api: Client) -> None:
    project = services.create_project("Synthetic")
    item = services.add_item("x", project_id=project.id)
    assert api.delete(f"/api/projects/{project.id}").status_code == 400
    services.delete_item(item.id)
    assert api.delete(f"/api/projects/{project.id}").status_code == 204
