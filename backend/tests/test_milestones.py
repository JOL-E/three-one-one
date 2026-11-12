"""Milestones (DECISIONS #71–80): items of type milestone, joined through an explicit link."""

import pytest
from django.db import IntegrityError, transaction

from inbox import services
from inbox.models import Activity, ActivityKind, Author, Item, ItemStatus, ItemType, Project
from inbox.services import RuleViolation

pytestmark = pytest.mark.django_db

ME = Author.OWNER
MILESTONE = ItemType.MILESTONE


@pytest.fixture
def project() -> Project:
    return services.create_project("Synthetic project")


@pytest.fixture
def m8(project: Project) -> Item:
    return services.add_item("M8", project_id=project.id, item_type=MILESTONE)


def task(title: str, milestone: Item | None = None, project: Project | None = None) -> Item:
    return services.add_item(
        title,
        project_id=project.id if project else None,
        milestone_id=milestone.id if milestone else None,
    )


def fresh(item: Item) -> Item:
    return Item.objects.get(pk=item.id)


def titles(items: list[Item]) -> list[str]:
    return [i.title for i in items]


def last_log(item: Item) -> Activity:
    return item.activities.order_by("created_at").last()  # type: ignore[return-value]


def finish(item: Item) -> None:
    services.set_status(item.id, ItemStatus.DONE, "Finished.", ME)


# --- Adding ------------------------------------------------------------------


def test_a_milestone_needs_a_project() -> None:
    with pytest.raises(RuleViolation, match="needs a project"):
        services.add_item("M8", item_type=MILESTONE)


def test_a_task_added_to_a_milestone_lands_in_its_project_at_its_bottom(project: Project, m8: Item) -> None:
    loose = task("loose", project=project)
    a, b = task("a", m8), task("b", m8)
    assert (a.project_id, a.milestone_id) == (project.id, m8.id)
    # Positions count per level: the top level, and each milestone's tasks.
    assert [m8.position, loose.position, a.position, b.position] == [0, 1, 0, 1]


def test_adding_to_a_milestone_of_another_project_is_refused(m8: Item) -> None:
    other = services.create_project("Other")
    with pytest.raises(RuleViolation, match="in another project"):
        services.add_item("x", project_id=other.id, milestone_id=m8.id)


def test_only_tasks_join_and_only_milestones_are_joined(project: Project, m8: Item) -> None:
    with pytest.raises(RuleViolation, match="can't be in another milestone"):
        services.add_item("M9", project_id=project.id, item_type=MILESTONE, milestone_id=m8.id)
    plain = task("plain", project=project)
    with pytest.raises(RuleViolation, match="is not a milestone"):
        task("x", plain)


def test_list_puts_each_milestone_before_its_tasks_then_done(project: Project, m8: Item) -> None:
    loose = task("loose", project=project)
    task("a", m8)
    finish(task("done", m8))
    services.reorder_item(loose.id, 0)
    assert titles(services.list_project_items(project.id)) == ["loose", "M8", "a", "done"]


# --- Done milestones (#72) ---------------------------------------------------


def test_a_milestone_is_done_only_when_all_its_tasks_are(m8: Item) -> None:
    a = task("a", m8)
    with pytest.raises(RuleViolation, match="still has 1 open or doing task"):
        finish(m8)
    finish(a)
    finish(m8)
    assert fresh(m8).status == ItemStatus.DONE


def test_nothing_joins_or_reopens_in_a_done_milestone(project: Project, m8: Item) -> None:
    a = task("a", m8)
    finish(a)
    finish(m8)
    with pytest.raises(RuleViolation, match="is done. Reopen it first"):
        task("new", m8)
    with pytest.raises(RuleViolation, match="is done. Reopen it first"):
        services.move_item(task("loose", project=project).id, None, ME, milestone_id=m8.id)
    with pytest.raises(RuleViolation, match="is done. Reopen it first"):
        services.set_status(a.id, ItemStatus.OPEN, "Not quite.", ME)


def test_a_reopened_task_goes_to_the_bottom_of_its_milestone(m8: Item) -> None:
    a, b = task("a", m8), task("b", m8)
    finish(a)
    services.set_status(a.id, ItemStatus.OPEN, "Not quite.", ME)
    assert (fresh(b).position, fresh(a).position) == (0, 1)


# --- Moving (#74, #78) -------------------------------------------------------


def test_joining_and_leaving_a_milestone_is_logged_and_renumbers(project: Project, m8: Item) -> None:
    a, loose = task("a", m8), task("loose", project=project)
    services.move_item(loose.id, None, ME, milestone_id=m8.id)
    assert (fresh(loose).milestone_id, fresh(loose).position) == (m8.id, 1)
    assert (fresh(m8).position, last_log(loose).old_value, last_log(loose).new_value) == (
        0,
        "Synthetic project",
        "M8",
    )

    services.move_item(a.id, project.id, ME)  # own project = out of the milestone
    assert (fresh(a).milestone_id, fresh(a).position, fresh(loose).position) == (None, 1, 0)
    assert (last_log(a).old_value, last_log(a).new_value) == ("M8", "Synthetic project")


def test_moving_to_where_the_item_already_is_is_refused(project: Project, m8: Item) -> None:
    a, loose = task("a", m8), task("loose", project=project)
    with pytest.raises(RuleViolation, match="already there"):
        services.move_item(a.id, None, ME, milestone_id=m8.id)
    with pytest.raises(RuleViolation, match="already there"):
        services.move_item(loose.id, project.id, ME)


def test_an_inbox_item_can_join_a_milestone(m8: Item) -> None:
    idea = task("idea")
    services.move_item(idea.id, None, ME, milestone_id=m8.id)
    assert (fresh(idea).project_id, last_log(idea).old_value) == (m8.project_id, "Inbox")


def test_a_task_moved_to_another_project_leaves_its_milestone(m8: Item) -> None:
    a, b = task("a", m8), task("b", m8)
    other = services.create_project("Other")
    services.move_item(a.id, other.id, ME)
    assert (fresh(a).project_id, fresh(a).milestone_id, fresh(a).position) == (other.id, None, 0)
    assert fresh(b).position == 0


def test_a_milestone_takes_all_its_tasks_to_another_project(project: Project, m8: Item) -> None:
    a, b = task("a", m8), task("b", m8)
    finish(b)
    other = services.create_project("Other")
    services.move_item(m8.id, other.id, ME)
    for t in (a, b):
        assert (fresh(t).project_id, fresh(t).milestone_id) == (other.id, m8.id)
        assert (last_log(t).old_value, last_log(t).new_value) == ("Synthetic project", "Other")
    assert (fresh(m8).position, fresh(a).position) == (0, 0)
    assert not project.items.exists()


def test_a_milestone_cannot_join_one_or_go_to_the_inbox(project: Project, m8: Item) -> None:
    m9 = services.add_item("M9", project_id=project.id, item_type=MILESTONE)
    with pytest.raises(RuleViolation, match="can't be in another milestone"):
        services.move_item(m9.id, None, ME, milestone_id=m8.id)
    with pytest.raises(RuleViolation, match="can't go to the inbox"):
        services.move_item(m9.id, None, ME)


# --- Type changes (#74) ------------------------------------------------------


def test_a_task_becomes_a_milestone_and_back_logged(project: Project) -> None:
    item = task("grows", project=project)
    services.update_item(item.id, item_type=MILESTONE, author=Author.CLAUDE)
    log = last_log(item)
    assert (log.kind, log.author, log.old_value, log.new_value) == ("type", "claude", "Task", "Milestone")
    services.update_item(item.id, item_type=ItemType.TASK)
    assert fresh(item).type == ItemType.TASK


def test_type_changes_that_would_break_a_rule_are_refused(m8: Item) -> None:
    with pytest.raises(RuleViolation, match="inbox holds only tasks"):
        services.update_item(task("idea").id, item_type=MILESTONE)
    a = task("a", m8)
    with pytest.raises(RuleViolation, match="out of its milestone first"):
        services.update_item(a.id, item_type=MILESTONE)
    with pytest.raises(RuleViolation, match="1 task"):
        services.update_item(m8.id, item_type=ItemType.TASK)


def test_editing_without_a_type_change_logs_nothing(m8: Item) -> None:
    services.update_item(m8.id, title="M8: Milestones", item_type=MILESTONE)
    assert not m8.activities.filter(kind=ActivityKind.TYPE).exists()


# --- Order (#73, #78) --------------------------------------------------------


def test_each_level_is_ordered_on_its_own(project: Project, m8: Item) -> None:
    loose = task("loose", project=project)
    a, b = task("a", m8), task("b", m8)
    services.set_order(project.id, [b.id, a.id], milestone_id=m8.id)
    services.set_order(project.id, [loose.id, m8.id])
    assert titles(services.list_project_items(project.id)) == ["loose", "M8", "b", "a"]
    assert services.reorder_item(a.id, 0).position == 0  # within its milestone


def test_an_order_must_name_exactly_the_items_of_its_level(project: Project, m8: Item) -> None:
    a, loose = task("a", m8), task("loose", project=project)
    with pytest.raises(RuleViolation, match="milestone 'M8' exactly once"):
        services.set_order(project.id, [a.id, loose.id], milestone_id=m8.id)
    with pytest.raises(RuleViolation, match="exactly once"):
        services.set_order(project.id, [m8.id, loose.id, a.id])
    other = services.create_project("Other")
    with pytest.raises(RuleViolation, match="not a milestone in 'Other'"):
        services.set_order(other.id, [a.id], milestone_id=m8.id)


# --- Deleting (#79) ----------------------------------------------------------


def test_deleting_a_milestone_keeps_its_tasks(project: Project, m8: Item) -> None:
    loose = task("loose", project=project)
    a, b = task("a", m8), task("b", m8)
    finish(b)
    services.delete_item(m8.id)
    assert (fresh(loose).position, fresh(a).position, fresh(b).position) == (0, 1, None)
    assert fresh(a).milestone_id is None and fresh(b).milestone_id is None
    assert (last_log(a).old_value, last_log(a).new_value) == ("M8", "Synthetic project")


# --- Database constraints (the one-row rules, #77) ---------------------------


def assert_rejected(**fields: object) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Item.objects.create(title="x", **fields)


def test_db_rejects_a_milestone_in_the_inbox() -> None:
    assert_rejected(type=MILESTONE)


def test_db_rejects_a_milestone_in_a_milestone(project: Project, m8: Item) -> None:
    assert_rejected(project=project, position=1, type=MILESTONE, milestone=m8)


def test_db_rejects_an_item_as_its_own_milestone(m8: Item) -> None:
    item = task("x", project=m8.project)
    with pytest.raises(IntegrityError), transaction.atomic():
        Item.objects.filter(pk=item.id).update(milestone=item)
