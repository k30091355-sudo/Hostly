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
    # 4 – Stufe 6 bis 8b: Gewinnspiele, Aktionen, Nachtpause, Backups, Erweiterungen, Statistik
    """
    CREATE TABLE giveaways (
        id                INTEGER PRIMARY KEY,
        title             TEXT NOT NULL,
        description       TEXT,
        coins_per_winner  INTEGER NOT NULL,
        winner_count      INTEGER NOT NULL,
        ends_at           TEXT NOT NULL,
        drawn_at          TEXT,
        created_by        INTEGER REFERENCES users(id),
        created_at        TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE giveaway_entries (
        giveaway_id  INTEGER NOT NULL REFERENCES giveaways(id),
        user_id      INTEGER NOT NULL REFERENCES users(id),
        is_winner    INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (giveaway_id, user_id)
    );

    -- kind: rabatt (Prozent) | ram (Extra-RAM für neue Mieten)
    CREATE TABLE promotions (
        id            INTEGER PRIMARY KEY,
        kind          TEXT NOT NULL,
        title         TEXT NOT NULL,
        percent       INTEGER NOT NULL DEFAULT 0,
        extra_ram_gb  REAL NOT NULL DEFAULT 0,
        model_ids     TEXT NOT NULL,
        starts_at     TEXT NOT NULL,
        ends_at       TEXT NOT NULL,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    ALTER TABLE servers ADD COLUMN extra_ram_gb REAL NOT NULL DEFAULT 0;
    ALTER TABLE servers ADD COLUMN extra_ram_until TEXT;
    ALTER TABLE servers ADD COLUMN night_pause_start INTEGER;
    ALTER TABLE servers ADD COLUMN night_pause_end INTEGER;
    ALTER TABLE servers ADD COLUMN public_listed INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE servers ADD COLUMN level_name TEXT NOT NULL DEFAULT 'world';
    ALTER TABLE servers ADD COLUMN world_seed TEXT;
    ALTER TABLE servers ADD COLUMN world_type TEXT;
    ALTER TABLE servers ADD COLUMN resource_pack_url TEXT;
    ALTER TABLE servers ADD COLUMN resource_pack_sha1 TEXT;
    ALTER TABLE servers ADD COLUMN resource_pack_enforce INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE servers ADD COLUMN crash_locked INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE servers ADD COLUMN template TEXT;

    CREATE TABLE night_pause_log (
        id             INTEGER PRIMARY KEY,
        server_id      INTEGER NOT NULL REFERENCES servers(id),
        start_at       TEXT NOT NULL,
        end_at         TEXT NOT NULL,
        planned_hours  INTEGER NOT NULL,
        status         TEXT NOT NULL,          -- laeuft | erstattet | unterbrochen | abgebrochen
        refund_coins   INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (server_id, start_at)
    );

    CREATE TABLE backups (
        id          INTEGER PRIMARY KEY,
        server_id   INTEGER NOT NULL REFERENCES servers(id),
        folder      TEXT NOT NULL,
        kind        TEXT NOT NULL,            -- taeglich | vor-aenderung | vor-wiederherstellung
        status      TEXT NOT NULL,            -- laeuft | fertig | fehler
        size_bytes  INTEGER NOT NULL DEFAULT 0,
        pinned      INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX backups_server ON backups(server_id, id);

    -- source: modrinth | upload (vom Admin)
    CREATE TABLE server_extensions (
        id              INTEGER PRIMARY KEY,
        server_id       INTEGER NOT NULL REFERENCES servers(id),
        source          TEXT NOT NULL,
        kind            TEXT NOT NULL,        -- plugin | mod | datapack
        project_id      TEXT,
        slug            TEXT,
        title           TEXT NOT NULL,
        version_id      TEXT,
        version_number  TEXT,
        filename        TEXT NOT NULL,
        url             TEXT,
        sha1            TEXT,
        sha512          TEXT,
        size            INTEGER NOT NULL DEFAULT 0,
        client_side     TEXT,
        is_dependency   INTEGER NOT NULL DEFAULT 0,
        enabled         INTEGER NOT NULL DEFAULT 1,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX server_extensions_server ON server_extensions(server_id);

    CREATE TABLE waitlist (
        id           INTEGER PRIMARY KEY,
        user_id      INTEGER NOT NULL REFERENCES users(id),
        model_id     INTEGER NOT NULL REFERENCES models(id),
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        notified_at  TEXT,
        UNIQUE (user_id, model_id)
    );

    CREATE TABLE crashes (
        id          INTEGER PRIMARY KEY,
        server_id   INTEGER NOT NULL REFERENCES servers(id),
        log_excerpt TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE player_samples (
        server_id  INTEGER NOT NULL REFERENCES servers(id),
        at         TEXT NOT NULL,
        running    INTEGER NOT NULL,
        players    INTEGER NOT NULL
    );
    CREATE INDEX player_samples_server ON player_samples(server_id, at);

    ALTER TABLE server_status ADD COLUMN restart_count INTEGER NOT NULL DEFAULT 0;
    """,
    # 5 – Einmalig: alle Accounts löschen (Wunsch des Besitzers, Nov. 2026 – Admin-Passwort vergessen).
    #     Danach wird der erste neu registrierte Account wieder Admin. Tunnel, Codes, Aktionen bleiben.
    """
    DELETE FROM jobs;
    DELETE FROM server_rentals;
    DELETE FROM server_status;
    DELETE FROM whitelist;
    DELETE FROM player_sessions;
    DELETE FROM server_log_state;
    DELETE FROM night_pause_log;
    DELETE FROM backups;
    DELETE FROM server_extensions;
    DELETE FROM crashes;
    DELETE FROM player_samples;
    DELETE FROM servers;
    DELETE FROM giveaway_entries;
    DELETE FROM waitlist;
    DELETE FROM notifications;
    DELETE FROM code_redemptions;
    DELETE FROM coin_ledger;
    DELETE FROM audit_log;
    DELETE FROM sessions;
    DELETE FROM login_attempts;
    UPDATE codes SET created_by = NULL, uses = 0;
    UPDATE giveaways SET created_by = NULL;
    DELETE FROM users;
    """,
    # 6 – Mehr CPU für schnellere Starts (Wunsch des Besitzers). Windows-Programme behalten Vorrang (cpu_shares).
    """
    UPDATE models SET cpu_limit = 2.0 WHERE key = 'holz';
    UPDATE models SET cpu_limit = 3.0 WHERE key = 'eisen';
    UPDATE models SET cpu_limit = 4.0 WHERE key = 'diamant';
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
    import fcntl
    import os

    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Website und worker starten gleichzeitig – die Sperrdatei sorgt dafür,
    # dass Migrationen nie doppelt parallel laufen.
    lock_path = path.parent / ".migrate.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        try:
            os.chmod(lock_path, 0o666)
        except OSError:
            pass
        fcntl.flock(fd, fcntl.LOCK_EX)
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
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


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
