"""Datenbank (SQLite im WAL-Modus) und Schema-Updates.

Neue Tabellen kommen in späteren Stufen als weitere Einträge in MIGRATIONS dazu.
Die Nummer der zuletzt ausgeführten Migration steht in `PRAGMA user_version`.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

MIGRATIONS: list[str] = [
    # 1 – Stufe 1: User, Sitzungen, Login-Versuche, Einstellungen, Protokoll
    """
    CREATE TABLE users (
        id                    INTEGER PRIMARY KEY,
        username              TEXT NOT NULL COLLATE NOCASE,
        password_hash         TEXT NOT NULL,
        is_admin              INTEGER NOT NULL DEFAULT 0,
        language              TEXT NOT NULL DEFAULT 'de',
        theme                 TEXT NOT NULL DEFAULT 'system',
        must_change_password  INTEGER NOT NULL DEFAULT 0,
        created_at            TEXT NOT NULL DEFAULT (datetime('now')),
        deleted_at            TEXT
    );
    -- Benutzername eindeutig (Groß/klein egal), gelöschte Konten geben den Namen frei
    CREATE UNIQUE INDEX users_username ON users(username) WHERE deleted_at IS NULL;

    CREATE TABLE sessions (
        id          INTEGER PRIMARY KEY,
        user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash  TEXT NOT NULL UNIQUE,
        admin_view  INTEGER NOT NULL DEFAULT 1,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen   TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at  TEXT NOT NULL,
        ip          TEXT,
        user_agent  TEXT
    );
    CREATE INDEX sessions_user ON sessions(user_id);

    CREATE TABLE login_attempts (
        id          INTEGER PRIMARY KEY,
        username    TEXT NOT NULL COLLATE NOCASE,
        ip          TEXT,
        success     INTEGER NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX login_attempts_user ON login_attempts(username, created_at);
    CREATE INDEX login_attempts_ip ON login_attempts(ip, created_at);

    CREATE TABLE settings (
        key    TEXT PRIMARY KEY,
        value  TEXT NOT NULL
    );

    CREATE TABLE audit_log (
        id          INTEGER PRIMARY KEY,
        user_id     INTEGER REFERENCES users(id),
        action      TEXT NOT NULL,
        details     TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    # isolation_level=None: jede Anweisung wird sofort gespeichert, außer innerhalb
    # von `transaction()` (dort alles oder nichts).
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_db(path: Path | None = None) -> None:
    """Legt die Datenbank an bzw. bringt sie auf den neuesten Stand."""
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for number, sql in enumerate(MIGRATIONS, start=1):
            if number <= version:
                continue
            conn.executescript("BEGIN;\n" + sql + f"\nPRAGMA user_version = {number};\nCOMMIT;")
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Alles-oder-nichts: bei einem Fehler wird alles zurückgenommen."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def audit(conn: sqlite3.Connection, user_id: int | None, action: str, details: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details),
    )
