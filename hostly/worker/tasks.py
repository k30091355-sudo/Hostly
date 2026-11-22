"""Zeitgesteuerte Aufgaben des workers: Status, Join-Verlauf, Ablauf, Aufräumen."""
import logging
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .. import config, db, minecraft, rcon, servers
from ..timeutil import fmt, now_sql

log = logging.getLogger("hostly.worker")

LIST_RE = re.compile(r"There are (\d+) of a max(?: of)? (\d+) players online:?(.*)", re.S)
JOIN_RE = re.compile(r"^\[(\d\d:\d\d:\d\d)\].*?\]: ([A-Za-z0-9_]{1,16}) joined the game")
LEFT_RE = re.compile(r"^\[(\d\d:\d\d:\d\d)\].*?\]: ([A-Za-z0-9_]{1,16}) left the game")
VERSION_RE = re.compile(r"Starting minecraft server version (\S+)")


# ---------- Status ----------

def update_status(w, conn, server_id: int) -> None:
    """Status eines Servers speichern. Eingefrorene Server werden NIE angefragt (würde sie wecken)."""
    server = w.load(conn, server_id)
    if server is None or server["state"] not in ("active", "creating", "reactivating", "archiving"):
        return
    st = w.ops.state(minecraft.container_name(server_id))
    paused = st["running"] and w.is_paused(server_id)
    model = servers.model(conn, server["model_id"])
    online, players = 0, ""
    if st["running"] and not paused and st["health"] == "healthy":
        try:
            out = w.server_rcon(conn, server, "list", attempts=1)
            m = LIST_RE.search(out or "")
            if m:
                online = int(m.group(1))
                players = ", ".join(p.strip() for p in m.group(3).split(",") if p.strip())
        except rcon.RconError:
            pass
    conn.execute(
        """INSERT INTO server_status (server_id, running, paused, health, players_online, players_max, players, checked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(server_id) DO UPDATE SET running = excluded.running, paused = excluded.paused,
             health = excluded.health, players_online = excluded.players_online,
             players_max = excluded.players_max, players = excluded.players, checked_at = excluded.checked_at""",
        (server_id, int(st["running"]), int(paused), st["health"], online, model["max_players"], players, now_sql()),
    )


def status_all(w) -> None:
    conn = w.conn()
    try:
        for row in conn.execute("SELECT id FROM servers WHERE state = 'active'").fetchall():
            try:
                update_status(w, conn, row["id"])
                read_log(conn, row["id"])
            except Exception:
                log.exception("Status für Server %s fehlgeschlagen", row["id"])
    finally:
        conn.close()


# ---------- Protokoll lesen: Join-Verlauf + echte Version ----------

def _log_time(hms: str) -> str:
    tz = ZoneInfo(config.TIMEZONE)
    local_now = datetime.now(tz)
    h, m, s = (int(x) for x in hms.split(":"))
    dt = local_now.replace(hour=h, minute=m, second=s, microsecond=0)
    if dt > local_now + timedelta(minutes=1):
        dt -= timedelta(days=1)
    return fmt(dt)


def read_log(conn, server_id: int) -> None:
    """Neue Zeilen aus logs/latest.log lesen (Datei lesen weckt den Server nicht)."""
    path = minecraft.data_dir(server_id) / "logs" / "latest.log"
    if not path.exists():
        return
    stat = path.stat()
    state = conn.execute("SELECT inode, offset FROM server_log_state WHERE server_id = ?", (server_id,)).fetchone()
    offset = 0
    if state and state["inode"] == stat.st_ino and state["offset"] <= stat.st_size:
        offset = state["offset"]
    if offset == stat.st_size:
        return
    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read(2_000_000)
        new_offset = offset + len(data)
    # nur vollständige Zeilen verarbeiten
    cut = data.rfind(b"\n")
    if cut == -1:
        return
    new_offset = offset + cut + 1
    lines = data[:cut].decode("utf-8", errors="replace").splitlines()

    with db.transaction(conn):
        server = conn.execute("SELECT mc_version FROM servers WHERE id = ?", (server_id,)).fetchone()
        for line in lines:
            if server and server["mc_version"] == "LATEST":
                v = VERSION_RE.search(line)
                if v:
                    # Version festhalten, damit der Server nicht ungewollt auf neue Versionen springt
                    conn.execute("UPDATE servers SET mc_version = ? WHERE id = ?", (v.group(1), server_id))
                    server = {"mc_version": v.group(1)}
            j = JOIN_RE.search(line)
            if j:
                conn.execute("INSERT INTO player_sessions (server_id, minecraft_name, joined_at) VALUES (?, ?, ?)",
                             (server_id, j.group(2), _log_time(j.group(1))))
                continue
            left = LEFT_RE.search(line)
            if left:
                conn.execute(
                    """UPDATE player_sessions SET left_at = ? WHERE id = (
                         SELECT id FROM player_sessions WHERE server_id = ? AND minecraft_name = ? AND left_at IS NULL
                         ORDER BY id DESC LIMIT 1)""",
                    (_log_time(left.group(1)), server_id, left.group(2)),
                )
        conn.execute(
            """INSERT INTO server_log_state (server_id, inode, offset) VALUES (?, ?, ?)
               ON CONFLICT(server_id) DO UPDATE SET inode = excluded.inode, offset = excluded.offset""",
            (server_id, stat.st_ino, new_offset),
        )


# ---------- Ablauf ----------

def check_expiry(w) -> None:
    """Abgelaufene Server: Auto-Verlängern versuchen, sonst archivieren."""
    conn = w.conn()
    try:
        due = conn.execute(
            "SELECT * FROM servers WHERE state = 'active' AND rented_until <= ?", (now_sql(),)
        ).fetchall()
        for server in due:
            with db.transaction(conn):
                server = w.load(conn, server["id"])
                if server["state"] != "active" or server["rented_until"] > now_sql():
                    continue
                if server["auto_renew"]:
                    if servers.try_auto_renew(conn, server):
                        db.notify(conn, server["owner_id"], "auto_renewed",
                                  f"„{server['name']}“ wurde automatisch um 7 Tage verlängert.", server["id"])
                        continue
                    db.notify(conn, server["owner_id"], "auto_renew_failed",
                              f"Auto-Verlängern fehlgeschlagen – zu wenig Coins. „{server['name']}“ wurde archiviert.",
                              server["id"])
                else:
                    db.notify(conn, server["owner_id"], "archived",
                              f"„{server['name']}“ ist abgelaufen und wurde archiviert. Du kannst ihn jederzeit reaktivieren.",
                              server["id"])
                conn.execute("UPDATE servers SET state = 'archiving' WHERE id = ?", (server["id"],))
                db.add_job(conn, "archive", server["id"])
    finally:
        conn.close()


# ---------- Aufräumen ----------

def cleanup_downloads() -> None:
    limit = time.time() - 24 * 3600
    if not config.DOWNLOADS_DIR.exists():
        return
    for f in config.DOWNLOADS_DIR.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < limit:
                f.unlink()
        except OSError:
            pass


def cleanup_db(w) -> None:
    conn = w.conn()
    try:
        conn.execute("DELETE FROM jobs WHERE status IN ('done', 'error') AND created_at < datetime('now', '-30 days')")
        conn.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
        conn.execute("DELETE FROM login_attempts WHERE created_at < datetime('now', '-1 day')")
    finally:
        conn.close()
