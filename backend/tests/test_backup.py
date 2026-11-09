"""`manage.py backup`: a usable copy of the database, the oldest pruned."""

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone

from inbox import services
from inbox.models import Author

# transaction=True: the backup reads committed data, as it does in production.
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


def run_backups(folder: Path, monkeypatch: Any, times: int, **options: Any) -> None:
    start = datetime(2026, 1, 1, 3, 0)
    for n in range(times):
        monkeypatch.setattr(timezone, "now", lambda n=n: start + timedelta(days=n))
        with override_settings(BACKUP_DIR=folder):
            call_command("backup", stdout=None, **options)


def test_backup_is_a_complete_database(tmp_path: Path, monkeypatch: Any) -> None:
    services.add_item(title="Synthetic idea", author=Author.OWNER)
    run_backups(tmp_path, monkeypatch, times=1)

    (copy,) = tmp_path.glob("311_*.sqlite3")
    assert copy.name == "311_2026-01-01_030000.sqlite3"
    with closing(sqlite3.connect(copy)) as db:
        titles = [row[0] for row in db.execute("SELECT title FROM inbox_item")]
    assert titles == ["Synthetic idea"]


def test_only_the_newest_are_kept(tmp_path: Path, monkeypatch: Any) -> None:
    run_backups(tmp_path, monkeypatch, times=4, keep=2)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["311_2026-01-03_030000.sqlite3", "311_2026-01-04_030000.sqlite3"]


def test_keep_must_be_positive(tmp_path: Path) -> None:
    with override_settings(BACKUP_DIR=tmp_path), pytest.raises(CommandError):
        call_command("backup", keep=0)
