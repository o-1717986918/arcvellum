"""Shared SQLite transaction and connection policy for persistence repositories."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from collections.abc import Iterator


class SqliteUnitOfWork:
    """Own connection configuration and serialize write transactions.

    Repositories depend on this object instead of reaching into ``JobStore`` for
    private locks and connection helpers.  A fresh connection is still opened
    per operation, preserving the existing process and WAL behaviour.
    """

    def __init__(self, path: Path):
        self.path = path
        self.write_lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level="DEFERRED")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self.connection() as connection:
            yield connection

    @contextmanager
    def write(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with self.write_lock, self.connection() as connection:
            if immediate:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
