"""Copy the live database to a backup file, safe while the app is running.

    python manage.py backup [--keep 7]

Uses SQLite's backup API: a consistent snapshot even while the app writes. A
plain file copy taken mid-write can be torn. The copy is checked before it
counts; the oldest backups beyond --keep are deleted. Prints the new file's path.
Restore: stop the app, put the file in place of DATA_DIR/311.sqlite3, start it.
"""

import sqlite3
from contextlib import closing
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection
from django.utils import timezone

PREFIX = "311_"
SUFFIX = ".sqlite3"


class Command(BaseCommand):
    help = "Back up the database to BACKUP_DIR and keep the newest few."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--keep", type=int, default=7, help="Backups to keep, newest first (default 7).")

    def handle(self, *args: Any, keep: int, **options: Any) -> None:
        if keep < 1:
            raise CommandError("--keep must be at least 1.")
        folder = settings.BACKUP_DIR
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{PREFIX}{timezone.now():%Y-%m-%d_%H%M%S}{SUFFIX}"
        partial = target.with_name(target.name + ".partial")  # never mistaken for a backup

        connection.ensure_connection()
        source = connection.connection  # Django's own sqlite3 connection
        with closing(sqlite3.connect(partial)) as copy:
            source.backup(copy)
            check = copy.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            partial.unlink()
            raise CommandError(f"The copy failed SQLite's integrity check: {check}")
        partial.replace(target)

        backups = sorted(folder.glob(f"{PREFIX}*{SUFFIX}"), reverse=True)  # names sort by time
        for old in backups[keep:]:
            old.unlink()
        self.stdout.write(str(target))
