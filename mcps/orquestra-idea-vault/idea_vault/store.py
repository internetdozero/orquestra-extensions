"""Local SQLite storage for the idea vault: path, connection, schema, validation."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

APP_DIR = "idea-vault"
DB_FILENAME = "ideas.sqlite3"
ENV_DB_PATH = "IDEA_VAULT_DB_PATH"

CATEGORIES = ("feature", "architecture", "bug", "ux", "idea")
PRIORITIES = ("low", "medium", "high", "critical")
STATUSES = ("open", "in_progress", "completed", "archived")
ACTIVE_STATUSES = ("open", "in_progress")

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    category    TEXT NOT NULL DEFAULT 'feature',
    priority    TEXT NOT NULL DEFAULT 'medium',
    tags        TEXT,
    status      TEXT NOT NULL DEFAULT 'open',
    prompt      TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blackboard_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    topic       TEXT NOT NULL,
    sender      TEXT NOT NULL,
    target      TEXT NOT NULL DEFAULT 'all',
    note        TEXT NOT NULL,
    is_read     BOOLEAN NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ideas_project_status ON ideas (project, status);
CREATE INDEX IF NOT EXISTS idx_ideas_category ON ideas (category);
CREATE INDEX IF NOT EXISTS idx_notes_project_topic ON blackboard_notes (project, topic, is_read);
"""


def default_db_path() -> Path:
    """Return the database path, honoring IDEA_VAULT_DB_PATH and XDG_DATA_HOME."""
    override = os.environ.get(ENV_DB_PATH, "").strip()
    if override:
        return Path(override).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base / APP_DIR / DB_FILENAME


def migrate_completed_at(conn: sqlite3.Connection) -> bool:
    """Add ideas.completed_at and backfill legacy completions. Idempotent."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(ideas)").fetchall()}
    if "completed_at" in columns:
        return False
    conn.execute("ALTER TABLE ideas ADD COLUMN completed_at TIMESTAMP")
    conn.execute(
        "UPDATE ideas SET completed_at = updated_at "
        "WHERE status = 'completed' AND completed_at IS NULL"
    )
    conn.commit()
    return True


def migrate_prompt(conn: sqlite3.Connection) -> bool:
    """Add ideas.prompt for orchestrator Builder prompts. Idempotent."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(ideas)").fetchall()}
    if "prompt" in columns:
        return False
    conn.execute("ALTER TABLE ideas ADD COLUMN prompt TEXT NOT NULL DEFAULT ''")
    conn.commit()
    return True


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating directories and schema as needed) a connection to the vault."""
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    migrate_completed_at(conn)
    migrate_prompt(conn)
    return conn


def require_text(value: object, field: str) -> str:
    """Return a stripped, non-empty string or raise ValueError."""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string")
    return text


def require_choice(value: object, allowed: tuple[str, ...], field: str) -> str:
    """Normalize a required value against a closed set of options."""
    text = str(value or "").strip().lower()
    if text not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return text


def clamp_limit(value: object, default: int, maximum: int | None = None) -> int:
    """Coerce a limit to a sane int: garbage falls back to `default`, floor 1."""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        number = default
    number = max(1, number)
    return min(number, maximum) if maximum is not None else number


def optional_choice(value: object, allowed: tuple[str, ...], field: str) -> str | None:
    """Normalize an optional filter value, treating empty/'all' as no filter."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text == "all":
        return None
    if text not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return text


class Database:
    """A lazily connected, lock-guarded SQLite handle committed per tool call."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else default_db_path()
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = connect(self.path)
            return self._conn

    def __enter__(self) -> sqlite3.Connection:
        self._lock.acquire()
        try:
            return self.connection
        except Exception:
            self._lock.release()
            raise

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if self._conn is not None:
                if exc_type is None:
                    self._conn.commit()
                else:
                    self._conn.rollback()
        finally:
            self._lock.release()
        return False

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


_DATABASES: dict[str, Database] = {}
_DATABASES_LOCK = threading.Lock()
_DEFAULT_PATH: Path | None = None


def configure(path: str | Path | None = None) -> Path:
    """Pin the database path used by tools (--db), or fall back to the env default."""
    global _DEFAULT_PATH
    _DEFAULT_PATH = Path(path).expanduser() if path else None
    return _DEFAULT_PATH or default_db_path()


def get_database(path: str | Path | None = None) -> Database:
    """Return the shared Database for a path (defaults to the configured vault)."""
    db = Database(path or _DEFAULT_PATH)
    key = str(db.path)
    with _DATABASES_LOCK:
        if key not in _DATABASES:
            _DATABASES[key] = db
        return _DATABASES[key]


def reset_databases() -> None:
    """Close cached handles. Used by tests and after changing IDEA_VAULT_DB_PATH."""
    global _DEFAULT_PATH
    with _DATABASES_LOCK:
        for db in _DATABASES.values():
            db.close()
        _DATABASES.clear()
        _DEFAULT_PATH = None
