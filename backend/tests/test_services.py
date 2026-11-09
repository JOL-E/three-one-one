"""Every rule in services.py, plus the database constraints behind them."""

import uuid

import pytest
from django.db import IntegrityError, transaction

from inbox import services
from inbox.models import Activity, ActivityKind, Author, Item, ItemStatus, Project, ProjectState
from inbox.services import RuleViolation

pytestmark = pytest.mark.django_db

ME = Author.OWNER
CLAUDE = Author.CLAUDE


@pytest.fixture
def project() -> Project:
    return services.create_project("Synthetic project")


def titles(items: list[Item]) -> list[str]:
    return [i.title for i in items]


def positions(project: Project) -> dict[str, int | None]:
    return {i.title: i.position for i in project.items.all()}


# --- Projects ----------------------------------------------------------------


def test_general_project_exists_from_migration() -> None:
    general = services.general_project()
    assert general.name == "General"
    assert general.state == ProjectState.BUILDING


def test_new_project_starts_as_idea() -> None:
    assert services.create_project("  Synthetic  ").state == ProjectState.IDEA


def test_project_name_required_and_unique_ignoring_case(project: Project) -> None:
    with pytest.raises(RuleViolation, match="needs a name"):
        services.create_project("  ")
    with pytest.raises(RuleViolation, match="already exists"):
        services.create_project("SYNTHETIC PROJECT")


def test_project_repo_url_must_be_http() -> None:
    with pytest.raises(RuleViolation, match="not a valid"):
        services.create_project("X", repo_url="ftp://example.com/repo")
    assert services.create_project("Y", repo_url="https://example.com/repo").repo_url


def test_project_state_can_go_anywhere(project: Project) -> None:
    services.set_project_state(project.id, ProjectState.LIVE)
    assert services.set_project_state(project.id, ProjectState.BUILDING).state == ProjectState.BUILDING


def test_general_project_state_is_fixed() -> None:
    with pytest.raises(RuleViolation, match="permanent"):
        services.set_project_state(services.general_project().id, ProjectState.ARCHIVED)


def test_archived_projects_hidden_by_default(project: Project) -> None:
    services.set_project_state(project.id, ProjectState.ARCHIVED)
    assert project not in services.list_projects()
    assert project in services.list_projects(include_archived=True)


def test_delete_project_refused_while_it_has_items(project: Project) -> None:
    services.add_item("Synthetic item", project_id=project.id)
    with pytest.raises(RuleViolation, match="items first"):
        services.delete_project(project.id)


def test_delete_empty_project(project: Project) -> None:
    services.delete_project(project.id)
    assert not Project.objects.filter(pk=project.id).exists()


def test_general_project_cannot_be_deleted() -> None:
    with pytest.raises(RuleViolation, match="permanent"):
        services.delete_project(services.general_project().id)


# --- Adding and listing items ------------------------------------------------


def test_add_item_without_project_lands_in_inbox() -> None:
    item = services.add_item("  Synthetic idea  ", "  notes ", author=CLAUDE)
    assert (item.title, item.details, item.project, item.position) == ("Synthetic idea", "notes", None, None)
    assert titles(services.list_inbox()) == ["Synthetic idea"]


def test_add_item_rejects_empty_title() -> None:
    with pytest.raises(RuleViolation, match="needs a title"):
        services.add_item("   ")


def test_add_item_logs_creation_with_author() -> None:
    item = services.add_item("Synthetic idea", author=CLAUDE)
    [entry] = services.list_activity(item.id)
    assert (entry.kind, entry.author) == (ActivityKind.CREATED, CLAUDE)


def test_add_item_to_project_goes_to_bottom(project: Project) -> None:
    services.add_item("a", project_id=project.id)
    services.add_item("b", project_id=project.id)
    assert positions(project) == {"a": 0, "b": 1}


def test_inbox_newest_first() -> None:
    services.add_item("first")
    services.add_item("second")
    assert titles(services.list_inbox()) == ["second", "first"]


def test_project_list_ranked_then_done(project: Project) -> None:
    for title in ["a", "b", "c"]:
        services.add_item(title, project_id=project.id)
    a, b = (Item.objects.get(title=t) for t in "ab")
    services.set_status(a.id, ItemStatus.DONE, "finished", ME)
    services.set_status(b.id, ItemStatus.DONE, "finished", ME)
    assert titles(services.list_project_items(project.id)) == ["c", "b", "a"]


def test_search_finds_items_everywhere_by_all_words(project: Project) -> None:
    services.add_item("CLI that lints Dockerfiles", project_id=project.id)
    services.add_item("Dockerfile cheat sheet")
    services.add_item("Unrelated")
    assert titles(services.search_items("dockerfile")) == [
        "Dockerfile cheat sheet",
        "CLI that lints Dockerfiles",
    ]
    assert titles(services.search_items("lints DOCKER")) == ["CLI that lints Dockerfiles"]


def test_search_skips_done_unless_asked(project: Project) -> None:
    item = services.add_item("Synthetic", project_id=project.id)
    services.set_status(item.id, ItemStatus.DONE, "done", ME)
    assert services.search_items("synthetic") == []
    assert len(services.search_items("synthetic", include_done=True)) == 1


def test_search_finds_items_by_the_start_of_their_id() -> None:
    hit = services.add_item("First", item_id=uuid.UUID("6a62" + "0" * 28))
    services.add_item("Second", item_id=uuid.UUID("6b00" + "0" * 28))
    assert titles(services.search_items("6A")) == ["First"]
    assert titles(services.search_items("#6a62")) == ["First"]
    assert services.search_items("6A")[0].id == hit.id


def test_search_lists_id_hits_before_title_hits() -> None:
    services.add_item("Notes on cafe culture", item_id=uuid.UUID("1" * 32))
    services.add_item("Older idea", item_id=uuid.UUID("cafe" + "0" * 28))
    assert titles(services.search_items("cafe")) == ["Older idea", "Notes on cafe culture"]


def test_search_by_id_needs_one_word_of_two_hex_characters() -> None:
    services.add_item("Synthetic", item_id=uuid.UUID("6a62" + "0" * 28))
    assert services.search_items("6") == []
    assert services.search_items("6a synthetic") == []
    assert services.search_items("6g") == []


def test_search_needs_a_word() -> None:
    with pytest.raises(RuleViolation, match="at least one word"):
        services.search_items("  ")


def test_update_item_edits_without_logging() -> None:
    item = services.add_item("Old")
    services.update_item(item.id, title=" New ", details="more")
    item.refresh_from_db()
    assert (item.title, item.details) == ("New", "more")
    assert len(services.list_activity(item.id)) == 1  # only "created"


def test_unknown_ids_are_rule_violations() -> None:
    with pytest.raises(RuleViolation, match="no item"):
        services.get_item(uuid.uuid4())


# --- Status ------------------------------------------------------------------


def test_status_change_requires_comment(project: Project) -> None:
    item = services.add_item("x", project_id=project.id)
    with pytest.raises(RuleViolation, match="needs a comment"):
        services.set_status(item.id, ItemStatus.DOING, "  ", CLAUDE)


def test_status_change_is_logged_with_comment(project: Project) -> None:
    item = services.add_item("x", project_id=project.id)
    services.set_status(item.id, ItemStatus.DOING, "Starting today", CLAUDE)
    entry = services.list_activity(item.id)[-1]
    assert (entry.kind, entry.text, entry.old_value, entry.new_value) == (
        ActivityKind.STATUS,
        "Starting today",
        "Open",
        "Doing",
    )


def test_inbox_item_status_cannot_change() -> None:
    item = services.add_item("x")
    with pytest.raises(RuleViolation, match="Sort the item"):
        services.set_status(item.id, ItemStatus.DOING, "why", ME)


def test_same_status_refused(project: Project) -> None:
    item = services.add_item("x", project_id=project.id)
    with pytest.raises(RuleViolation, match="already Open"):
        services.set_status(item.id, ItemStatus.OPEN, "why", ME)


def test_done_leaves_the_order_and_closes_the_gap(project: Project) -> None:
    a, _, _ = (services.add_item(t, project_id=project.id) for t in "abc")
    done = services.set_status(a.id, ItemStatus.DONE, "shipped", ME)
    assert done.done_at is not None
    assert positions(project) == {"a": None, "b": 0, "c": 1}


def test_reopened_item_goes_to_bottom(project: Project) -> None:
    a, _ = (services.add_item(t, project_id=project.id) for t in "ab")
    services.set_status(a.id, ItemStatus.DONE, "shipped", ME)
    reopened = services.set_status(a.id, ItemStatus.OPEN, "broke again", ME)
    assert reopened.done_at is None
    assert positions(project) == {"b": 0, "a": 1}


def test_doing_keeps_its_position(project: Project) -> None:
    a, _ = (services.add_item(t, project_id=project.id) for t in "ab")
    services.set_status(a.id, ItemStatus.DOING, "go", ME)
    assert positions(project) == {"a": 0, "b": 1}


# --- Moving ------------------------------------------------------------------


def test_sorting_from_inbox_needs_no_comment_but_is_logged(project: Project) -> None:
    item = services.add_item("x")
    moved = services.move_item(item.id, project.id, CLAUDE)
    assert (moved.project, moved.position, moved.status) == (project, 0, ItemStatus.OPEN)
    entry = services.list_activity(item.id)[-1]
    assert (entry.kind, entry.old_value, entry.new_value) == (ActivityKind.MOVED, "Inbox", project.name)


def test_move_between_projects_renumbers_both(project: Project) -> None:
    other = services.create_project("Other")
    services.add_item("o", project_id=other.id)
    a, _ = (services.add_item(t, project_id=project.id) for t in "ab")
    services.move_item(a.id, other.id, ME)
    assert positions(project) == {"b": 0}
    assert positions(other) == {"o": 0, "a": 1}


def test_done_item_moves_without_position(project: Project) -> None:
    other = services.create_project("Other")
    item = services.add_item("x", project_id=project.id)
    services.set_status(item.id, ItemStatus.DONE, "done", ME)
    assert services.move_item(item.id, other.id, ME).position is None


def test_only_open_items_go_back_to_inbox(project: Project) -> None:
    item = services.add_item("x", project_id=project.id)
    services.set_status(item.id, ItemStatus.DOING, "go", ME)
    with pytest.raises(RuleViolation, match="Only open"):
        services.move_item(item.id, None, ME)
    services.set_status(item.id, ItemStatus.OPEN, "later", ME)
    assert services.move_item(item.id, None, ME).position is None


def test_move_to_same_place_refused() -> None:
    item = services.add_item("x")
    with pytest.raises(RuleViolation, match="already there"):
        services.move_item(item.id, None, ME)


# --- Order -------------------------------------------------------------------


def test_reorder_moves_item_and_shifts_others(project: Project) -> None:
    *_, c = (services.add_item(t, project_id=project.id) for t in "abc")
    services.reorder_item(c.id, 0)
    assert positions(project) == {"c": 0, "a": 1, "b": 2}


def test_reorder_clamps_out_of_range(project: Project) -> None:
    a, _ = (services.add_item(t, project_id=project.id) for t in "ab")
    assert services.reorder_item(a.id, 99).position == 1


def test_reorder_refused_for_inbox_and_done(project: Project) -> None:
    with pytest.raises(RuleViolation, match="priority order"):
        services.reorder_item(services.add_item("inbox").id, 0)
    done = services.add_item("x", project_id=project.id)
    services.set_status(done.id, ItemStatus.DONE, "done", ME)
    with pytest.raises(RuleViolation, match="priority order"):
        services.reorder_item(done.id, 0)


def test_set_order_replaces_whole_order(project: Project) -> None:
    a, b, c = (services.add_item(t, project_id=project.id) for t in "abc")
    services.set_order(project.id, [c.id, a.id, b.id])
    assert positions(project) == {"c": 0, "a": 1, "b": 2}


def test_set_order_must_name_every_ranked_item_once(project: Project) -> None:
    a, b = (services.add_item(t, project_id=project.id) for t in "ab")
    stranger = services.add_item("not in this project")
    for ids in ([a.id], [a.id, a.id], [a.id, b.id, stranger.id]):
        with pytest.raises(RuleViolation, match="exactly once"):
            services.set_order(project.id, ids)
    assert positions(project) == {"a": 0, "b": 1}


def test_delete_item_closes_gap_and_removes_log(project: Project) -> None:
    a, _ = (services.add_item(t, project_id=project.id) for t in "ab")
    services.delete_item(a.id)
    assert positions(project) == {"b": 0}
    assert not Activity.objects.filter(item_id=a.id).exists()


# --- Comments ----------------------------------------------------------------


def test_comment_logged_and_must_not_be_empty() -> None:
    item = services.add_item("x")
    with pytest.raises(RuleViolation, match="can't be empty"):
        services.add_comment(item.id, " ", ME)
    services.add_comment(item.id, "  A thought  ", CLAUDE)
    assert services.list_activity(item.id)[-1].text == "A thought"


# --- Database constraints (the backstop when something bypasses the services) --


def assert_rejected(**fields: object) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Item.objects.create(title="x", **fields)


def test_db_rejects_second_general_project() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Project.objects.create(name="Another", is_general=True, state=ProjectState.BUILDING)


def test_db_rejects_inbox_item_not_open() -> None:
    assert_rejected(status=ItemStatus.DOING)


def test_db_rejects_bad_positions(project: Project) -> None:
    assert_rejected(position=0)  # inbox item with a position
    assert_rejected(project=project)  # ranked item without one


def test_db_rejects_done_without_done_at(project: Project) -> None:
    assert_rejected(project=project, status=ItemStatus.DONE)


def test_db_rejects_status_change_without_comment() -> None:
    item = services.add_item("x")
    with pytest.raises(IntegrityError), transaction.atomic():
        Activity.objects.create(item=item, author=ME, kind=ActivityKind.STATUS)


# --- Short ids (DECISIONS #40) -------------------------------------------------


def make(hex_start: str) -> Item:
    return services.add_item(f"Item {hex_start}", item_id=uuid.UUID(hex_start.ljust(32, "0")))


def test_short_id_is_four_characters_when_unique() -> None:
    item = make("abcd")
    make("1234")
    assert services.short_ids()[item.id] == "ABCD"


def test_short_id_grows_until_unique() -> None:
    a, b, c = make("3f9a7"), make("3f9a8"), make("3f00")
    ids = services.short_ids()
    assert (ids[a.id], ids[b.id], ids[c.id]) == ("3F9A7", "3F9A8", "3F00")


def test_resolve_accepts_short_full_and_decorated_ids() -> None:
    item = make("3f9a")
    for ref in ["3F9A", "#3f9a", str(item.id), item.id.hex]:
        assert services.resolve_item(ref) == item


def test_resolve_refuses_ambiguous_too_short_and_unknown() -> None:
    make("3f9a7"), make("3f9a8")
    with pytest.raises(RuleViolation, match="matches several items"):
        services.resolve_item("3f9a")
    with pytest.raises(RuleViolation, match="at least 4"):
        services.resolve_item("3f9")
    with pytest.raises(services.NotFound):
        services.resolve_item("ffff")


def test_app_generated_item_id_is_kept_and_cannot_repeat() -> None:
    item_id = uuid.uuid4()
    assert services.add_item("x", item_id=item_id).id == item_id
    with pytest.raises(RuleViolation, match="already exists"):
        services.add_item("y", item_id=item_id)


# --- Editing projects (DECISIONS #37) -------------------------------------------


def test_update_project_changes_only_what_is_given(project: Project) -> None:
    services.update_project(project.id, description="New notes")
    project.refresh_from_db()
    assert (project.name, project.description) == ("Synthetic project", "New notes")


def test_update_project_keeps_names_unique_but_allows_own_name(project: Project) -> None:
    services.create_project("Other")
    with pytest.raises(RuleViolation, match="already exists"):
        services.update_project(project.id, name="other")
    services.update_project(project.id, name="SYNTHETIC PROJECT")  # same project, new casing


def test_update_project_checks_repo_url(project: Project) -> None:
    with pytest.raises(RuleViolation, match="valid http"):
        services.update_project(project.id, repo_url="not a url")
    assert services.update_project(project.id, repo_url="").repo_url == ""


def test_general_project_keeps_its_name() -> None:
    general = services.general_project()
    with pytest.raises(RuleViolation, match="keeps its name"):
        services.update_project(general.id, name="Misc")
    services.update_project(general.id, description="Things to look into")


def test_missing_project_or_item_is_not_found() -> None:
    with pytest.raises(services.NotFound):
        services.get_project(uuid.uuid4())
    with pytest.raises(services.NotFound):
        services.get_item(uuid.uuid4())
