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
    # 2 – Stufe 2: Coins und Codes
    """
    -- Kontostand = Summe aller Buchungen (wird nie direkt gespeichert)
    CREATE TABLE coin_ledger (
        id          INTEGER PRIMARY KEY,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        amount      INTEGER NOT NULL,
        reason      TEXT NOT NULL,
        note        TEXT,
        ref_type    TEXT,
        ref_id      INTEGER,
        created_by  INTEGER REFERENCES users(id),
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX coin_ledger_user ON coin_ledger(user_id, id);

    CREATE TABLE codes (
        id          INTEGER PRIMARY KEY,
        code        TEXT NOT NULL UNIQUE,
        coins       INTEGER NOT NULL CHECK (coins BETWEEN 50 AND 1000),
        max_uses    INTEGER NOT NULL CHECK (max_uses >= 1),
        uses        INTEGER NOT NULL DEFAULT 0,
        expires_at  TEXT,
        active      INTEGER NOT NULL DEFAULT 1,
        created_by  INTEGER REFERENCES users(id),
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- "pro User nur 1x" steht direkt in der Datenbank
    CREATE TABLE code_redemptions (
        code_id     INTEGER NOT NULL REFERENCES codes(id),
        user_id     INTEGER NOT NULL REFERENCES users(id),
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (code_id, user_id)
    );

    CREATE TABLE notifications (
        id          INTEGER PRIMARY KEY,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        kind        TEXT NOT NULL,
        text        TEXT NOT NULL,
        server_id   INTEGER,
        read_at     TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX notifications_user ON notifications(user_id, read_at);
    """,
    # 3 – Stufe 3 bis 5: Modelle, Tunnel, Server, Aufträge, Status, Spieler
    """
    CREATE TABLE models (
        id             INTEGER PRIMARY KEY,
        key            TEXT NOT NULL UNIQUE,
        name           TEXT NOT NULL,
        ram_gb         REAL NOT NULL,
        max_players    INTEGER NOT NULL,
        price_per_day  INTEGER NOT NULL,
        cpu_limit      REAL NOT NULL,
        sort           INTEGER NOT NULL
    );
    INSERT INTO models (key, name, ram_gb, max_players, price_per_day, cpu_limit, sort) VALUES
        ('holz', 'Holz', 2, 3, 10, 1.0, 1),
        ('eisen', 'Eisen', 3, 7, 30, 1.5, 2),
        ('diamant', 'Diamant', 4, 15, 50, 2.0, 3);

    CREATE TABLE tunnels (
        id              INTEGER PRIMARY KEY,
        name            TEXT NOT NULL,
        playit_account  INTEGER NOT NULL DEFAULT 1,
        public_address  TEXT NOT NULL,
        internal_ip     TEXT NOT NULL UNIQUE,
        active          INTEGER NOT NULL DEFAULT 1,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- state: creating | active | archived | reactivating | deleted
    CREATE TABLE servers (
        id                 INTEGER PRIMARY KEY,
        owner_id           INTEGER NOT NULL REFERENCES users(id),
        name               TEXT NOT NULL,
        short_code         TEXT NOT NULL UNIQUE,
        model_id           INTEGER NOT NULL REFERENCES models(id),
        type               TEXT NOT NULL,
        mc_version         TEXT NOT NULL DEFAULT 'LATEST',
        state              TEXT NOT NULL,
        tunnel_id          INTEGER REFERENCES tunnels(id),
        rented_until       TEXT NOT NULL,
        paid_total         INTEGER NOT NULL DEFAULT 0,
        paid_days          INTEGER NOT NULL DEFAULT 0,
        discount_percent   INTEGER NOT NULL DEFAULT 0,
        auto_renew         INTEGER NOT NULL DEFAULT 0,
        rcon_password      TEXT NOT NULL,
        needs_restart      INTEGER NOT NULL DEFAULT 0,
        motd               TEXT,
        icon_path          TEXT,
        whitelist_enabled  INTEGER NOT NULL DEFAULT 0,
        warned_at          TEXT,
        created_at         TEXT NOT NULL DEFAULT (datetime('now')),
        archived_at        TEXT,
        deleted_at         TEXT
    );
    CREATE INDEX servers_owner ON servers(owner_id);
    -- ein Tunnel gehört höchstens einem Server
    CREATE UNIQUE INDEX servers_tunnel ON servers(tunnel_id) WHERE tunnel_id IS NOT NULL;

    CREATE TABLE server_rentals (
        id                INTEGER PRIMARY KEY,
        server_id         INTEGER NOT NULL REFERENCES servers(id),
        kind              TEXT NOT NULL,
        days              INTEGER NOT NULL,
        price             INTEGER NOT NULL,
        discount_percent  INTEGER NOT NULL,
        request_id        TEXT UNIQUE,
        created_at        TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Aufträge von der Website an den worker
    CREATE TABLE jobs (
        id          INTEGER PRIMARY KEY,
        kind        TEXT NOT NULL,
        server_id   INTEGER REFERENCES servers(id),
        user_id     INTEGER REFERENCES users(id),
        payload     TEXT,
        status      TEXT NOT NULL DEFAULT 'pending',
        result      TEXT,
        error       TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        started_at  TEXT,
        done_at     TEXT
    );
    CREATE INDEX jobs_status ON jobs(status, id);
    CREATE INDEX jobs_server ON jobs(server_id, id);

    CREATE TABLE server_status (
        server_id       INTEGER PRIMARY KEY REFERENCES servers(id),
        running         INTEGER NOT NULL DEFAULT 0,
        paused          INTEGER NOT NULL DEFAULT 0,
        health          TEXT,
        players_online  INTEGER NOT NULL DEFAULT 0,
        players_max     INTEGER NOT NULL DEFAULT 0,
        players         TEXT,
        checked_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE whitelist (
        server_id       INTEGER NOT NULL REFERENCES servers(id),
        minecraft_name  TEXT NOT NULL COLLATE NOCASE,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (server_id, minecraft_name)
    );

    CREATE TABLE player_sessions (
        id              INTEGER PRIMARY KEY,
        server_id       INTEGER NOT NULL REFERENCES servers(id),
        minecraft_name  TEXT NOT NULL,
        joined_at       TEXT NOT NULL,
        left_at         TEXT
    );
    CREATE INDEX player_sessions_server ON player_sessions(server_id, id);

    -- bis wohin das Minecraft-Protokoll schon gelesen wurde
    CREATE TABLE server_log_state (
        server_id  INTEGER PRIMARY KEY REFERENCES servers(id),
        inode      INTEGER,
        offset     INTEGER NOT NULL DEFAULT 0
    );

    ALTER TABLE users ADD COLUMN minecraft_name TEXT;
    ALTER TABLE users ADD COLUMN avatar_mode TEXT NOT NULL DEFAULT 'none';
    ALTER TABLE users ADD COLUMN avatar_version INTEGER NOT NULL DEFAULT 0;
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


# ---------- Einstellungen (Tabelle settings) ----------

def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def notify(conn: sqlite3.Connection, user_id: int, kind: str, text: str, server_id: int | None = None) -> None:
    """Meldung, die der User auf der Startseite sieht."""
    conn.execute(
        "INSERT INTO notifications (user_id, kind, text, server_id) VALUES (?, ?, ?, ?)",
        (user_id, kind, text, server_id),
    )


def add_job(conn: sqlite3.Connection, kind: str, server_id: int | None = None,
            user_id: int | None = None, payload: dict | None = None) -> int:
    """Auftrag für den worker eintragen."""
    import json

    cur = conn.execute(
        "INSERT INTO jobs (kind, server_id, user_id, payload) VALUES (?, ?, ?, ?)",
        (kind, server_id, user_id, json.dumps(payload or {})),
    )
    return cur.lastrowid
