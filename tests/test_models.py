"""Tests for shared data models and ID generation."""

from __future__ import annotations

from prothon.models import Promise, Task, _generate_id


def test_generate_id_returns_8_char_hex():
    """Generated IDs must be 8-character hex strings."""
    id_ = _generate_id()
    assert len(id_) == 8
    assert all(c in "0123456789abcdef" for c in id_)


def test_generate_id_uniqueness():
    """Consecutive IDs must not collide."""
    ids = {_generate_id() for _ in range(100)}
    assert len(ids) == 100


def test_task_auto_assigns_id():
    """Tasks created without an explicit ID get a generated one."""
    task = Task(title="do something")
    assert len(task.task_id) == 8
    assert task.task_id != Task(title="other").task_id


def test_task_preserves_explicit_id():
    """An explicitly provided task_id is not overwritten."""
    task = Task(title="explicit", task_id="custom01")
    assert task.task_id == "custom01"


def test_task_defaults_not_completed():
    """New tasks default to incomplete with zero attempts."""
    task = Task(title="t")
    assert task.completed is False
    assert task.attempts == 0
    assert task.max_attempts == 3


def test_promise_aggregates_tasks():
    """Promise holds metadata and an ordered task list."""
    p = Promise()
    p.tasks.append(Task(title="a"))
    p.tasks.append(Task(title="b"))
    assert len(p.tasks) == 2
    assert p.tasks[0].title == "a"


def test_promise_instances_do_not_share_task_lists():
    """Each Promise instance must have its own task list (no mutable default sharing)."""
    p1 = Promise()
    p2 = Promise()
    p1.tasks.append(Task(title="only in p1"))
    assert len(p2.tasks) == 0
