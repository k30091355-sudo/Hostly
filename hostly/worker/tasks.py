"""Zeitgesteuerte Aufgaben des workers: Status, Join-Verlauf, Ablauf, Aufräumen."""
import logging
import random
import re
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .. import coins, config, db, minecraft, nightpause, rcon, servers
from ..timeutil import fmt, now, now_sql, parse
from . import files

log = logging.getLogger("hostly.worker")

LIST_RE = re.compile(r"There are (\d+) of a max(?: of)? (\d+) players online:?(.*)", re.S)
# Vanilla/Fabric: "[17:54:15] [Server thread/INFO]: Steve joined the game"
# Paper:          "[17:54:15 INFO]: Steve joined the game"
_LOG_PREFIX = r"^\[(\d\d:\d\d:\d\d)[^\]]*\](?: \[[^\]]*\])?: "
JOIN_RE = re.compile(_LOG_PREFIX + r"([A-Za-z0-9_]{1,16}) joined the game")
LEFT_RE = re.compile(_LOG_PREFIX + r"([A-Za-z0-9_]{1,16}) left the game")
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
    cpu = mem = tps = None
    if st["running"] and not paused and st["health"] == "healthy":
        try:
            out = w.server_rcon(conn, server, "list", attempts=1)
            m = LIST_RE.search(out or "")
            if m:
                online = int(m.group(1))
                players = ", ".join(p.strip() for p in m.group(3).split(",") if p.strip())
            tps = parse_tps(w.server_rcon(conn, server, "tick query", attempts=1))
        except rcon.RconError:
            pass
        if hasattr(w.ops, "stats"):
            try:
                s = w.ops.stats(minecraft.container_name(server_id)) or {}
                cpu, mem = s.get("cpu_percent"), s.get("mem_mb")
            except Exception:
                log.debug("Docker-Werte für Server %s nicht lesbar", server_id)
    restarts = st.get("restart_count", 0)
    old = conn.execute("SELECT restart_count FROM server_status WHERE server_id = ?", (server_id,)).fetchone()
    conn.execute(
        """INSERT INTO server_status (server_id, running, paused, health, players_online, players_max, players,
                                      checked_at, restart_count, cpu_percent, mem_mb, tps)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(server_id) DO UPDATE SET running = excluded.running, paused = excluded.paused,
             health = excluded.health, players_online = excluded.players_online,
             players_max = excluded.players_max, players = excluded.players, checked_at = excluded.checked_at,
             restart_count = excluded.restart_count, cpu_percent = excluded.cpu_percent,
             mem_mb = excluded.mem_mb, tps = excluded.tps""",
        (server_id, int(st["running"]), int(paused), st["health"], online, model["max_players"], players, now_sql(),
         restarts, cpu, mem, tps),
    )
    if old is not None and restarts > old["restart_count"]:
        handle_crash(w, conn, server)


TICK_RE = re.compile(r"Average time per tick: ([\d.]+)ms")
RATE_RE = re.compile(r"Target tick rate: ([\d.]+)")


def parse_tps(out: str | None) -> float | None:
    """TPS aus `tick query` (Minecraft 1.20.3+): min(Ziel-Rate, 1000 / ms pro Tick)."""
    m = TICK_RE.search(out or "")
    if not m:
        return None
    rate = float(RATE_RE.search(out).group(1)) if RATE_RE.search(out) else 20.0
    mspt = float(m.group(1))
    return round(min(rate, 1000 / mspt) if mspt > 0 else rate, 1)


def handle_crash(w, conn, server) -> None:
    """Absturz-Schutz: Docker startet automatisch neu. Nach 3 Abstürzen in 10 Minuten ist Schluss."""
    excerpt = ""
    if hasattr(w.ops, "logs_tail"):
        excerpt = w.ops.logs_tail(minecraft.container_name(server["id"]), 25)[-3000:]
    conn.execute("INSERT INTO crashes (server_id, log_excerpt) VALUES (?, ?)", (server["id"], excerpt))
    recent = conn.execute(
        "SELECT COUNT(*) FROM crashes WHERE server_id = ? AND created_at > datetime('now', '-10 minutes')",
        (server["id"],)).fetchone()[0]
    if recent >= 3:
        w.ops.stop(minecraft.container_name(server["id"]), timeout=30)
        conn.execute("UPDATE servers SET crash_locked = 1 WHERE id = ?", (server["id"],))
        db.notify(conn, server["owner_id"], "crash",
                  f"„{server['name']}“ ist 3× hintereinander abgestürzt und wurde angehalten. "
                  "Schau in die Konsole (Reiter „Konsole“) und starte ihn dann neu.", server["id"])
    else:
        db.notify(conn, server["owner_id"], "crash",
                  f"„{server['name']}“ ist abgestürzt und wurde automatisch neu gestartet.", server["id"])


def record_samples(conn) -> None:
    """Spielerzahlen für die Statistik (1× pro Minute, 8 Tage aufbewahren)."""
    conn.execute(
        """INSERT INTO player_samples (server_id, at, running, players, cpu_percent, mem_mb, tps)
           SELECT st.server_id, ?, st.running, st.players_online, st.cpu_percent, st.mem_mb, st.tps
           FROM server_status st
           JOIN servers s ON s.id = st.server_id WHERE s.state = 'active'""", (now_sql(),))
    conn.execute("DELETE FROM player_samples WHERE at < datetime('now', '-8 days')")


def status_all(w) -> None:
    conn = w.conn()
    try:
        for row in conn.execute("SELECT id FROM servers WHERE state = 'active'").fetchall():
            try:
                update_status(w, conn, row["id"])
                read_log(conn, row["id"])
            except Exception:
                log.exception("Status für Server %s fehlgeschlagen", row["id"])
        record_samples(conn)
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


# ---------- Geplante Wartung (1.3.0) ----------

def planned_maintenance(w) -> None:
    conn = w.conn()
    try:
        start = db.get_setting(conn, "maintenance_planned_start") or ""
        end = db.get_setting(conn, "maintenance_planned_end") or ""
        auto_end = db.get_setting(conn, "maintenance_auto_end") or ""
        if start and start <= now_sql():
            db.set_setting(conn, "maintenance_mode", "1")
            db.set_setting(conn, "maintenance_planned_start", "")
            db.set_setting(conn, "maintenance_planned_end", "")
            db.set_setting(conn, "maintenance_auto_end", end)
            log.info("Geplante Wartung beginnt")
        elif auto_end and auto_end <= now_sql():
            db.set_setting(conn, "maintenance_mode", "0")
            db.set_setting(conn, "maintenance_auto_end", "")
            log.info("Geplante Wartung beendet")
    finally:
        conn.close()


def coins_reminder(w) -> None:
    """3 Tage vor dem Auto-Verlängern: Hinweis, wenn die Coins nicht reichen (einmal pro Ablauftermin)."""
    conn = w.conn()
    try:
        rows = conn.execute(
            """SELECT * FROM servers WHERE state = 'active' AND auto_renew = 1
               AND rented_until <= datetime('now', '+3 days') AND rented_until > datetime('now')""").fetchall()
        for s in rows:
            price = servers.price_for(conn, servers.model(conn, s["model_id"]), 7).final
            if coins.balance(conn, s["owner_id"]) >= price:
                continue
            seen = conn.execute(
                """SELECT 1 FROM notifications WHERE user_id = ? AND server_id = ? AND kind = 'coins_low'
                   AND created_at > datetime(?, '-4 days')""", (s["owner_id"], s["id"], s["rented_until"])).fetchone()
            if not seen:
                db.notify(conn, s["owner_id"], "coins_low",
                          f"Für das Auto-Verlängern von „{s['name']}“ fehlen Coins ({price} nötig). "
                          "Löse einen Code ein, sonst wird der Server archiviert.", s["id"])
    finally:
        conn.close()


# ---------- Ablauf ----------

def check_expiry(w) -> None:
    """Abgelaufene Server: Auto-Verlängern versuchen, sonst archivieren."""
    conn = w.conn()
    try:
        if db.get_setting(conn, "maintenance_mode") == "1":
            return  # im Wartungsmodus werden Abläufe danach nachgeholt
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


# ---------- Nachtpause ----------

def night_pauses(w, current: datetime | None = None) -> None:
    current = current or now()
    conn = w.conn()
    try:
        # 1) beendete Pausen abrechnen
        for log_row in conn.execute("SELECT * FROM night_pause_log WHERE status = 'laeuft' AND end_at <= ?",
                                    (fmt(current),)).fetchall():
            with db.transaction(conn):
                server = w.load(conn, log_row["server_id"])
                if server["state"] != "active" or server["night_pause_start"] is None:
                    conn.execute("UPDATE night_pause_log SET status = 'abgebrochen' WHERE id = ?", (log_row["id"],))
                    continue
                hours = nightpause.real_hours(parse(log_row["start_at"]), parse(log_row["end_at"]))
                amount = nightpause.refund(server["paid_total"], server["paid_days"], hours, server["discount_percent"])
                s_h, e_h = parse(log_row["start_at"]).astimezone(nightpause.tz()).hour, \
                    parse(log_row["end_at"]).astimezone(nightpause.tz()).hour
                if amount > 0:
                    coins.book(conn, server["owner_id"], amount, "nachtpause",
                               note=f"{server['name']} · {s_h:02d}–{e_h:02d} Uhr", ref_type="server", ref_id=server["id"])
                conn.execute("UPDATE night_pause_log SET status = 'erstattet', refund_coins = ? WHERE id = ?",
                             (amount, log_row["id"]))
                db.add_job(conn, "start", server["id"])   # Server wieder an (friert ein, bis jemand kommt)

        # 2) neue Pausen beginnen, Spieler vorher warnen
        rows = conn.execute(
            "SELECT * FROM servers WHERE state = 'active' AND night_pause_start IS NOT NULL").fetchall()
        for server in rows:
            win = nightpause.window_containing(current, server["night_pause_start"], server["night_pause_end"])
            if win:
                start_at = fmt(win[0])
                try:
                    conn.execute(
                        "INSERT INTO night_pause_log (server_id, start_at, end_at, planned_hours, status) VALUES (?, ?, ?, ?, 'laeuft')",
                        (server["id"], start_at, fmt(win[1]),
                         nightpause.planned_hours(server["night_pause_start"], server["night_pause_end"])))
                except sqlite3.IntegrityError:
                    continue  # diese Pause läuft schon
                db.add_job(conn, "stop", server["id"])
            else:
                minutes = (nightpause.next_start(current, server["night_pause_start"]) - current).total_seconds() / 60
                if 4 < minutes <= 5:
                    db.add_job(conn, "rcon", server["id"], payload={
                        "commands": ["say Nachtpause: Der Server geht in 5 Minuten offline."]})
    finally:
        conn.close()


# ---------- Gewinnspiele ----------

def draw_giveaways(w) -> None:
    conn = w.conn()
    try:
        for g in conn.execute("SELECT * FROM giveaways WHERE drawn_at IS NULL AND ends_at <= ?", (now_sql(),)).fetchall():
            with db.transaction(conn):
                entries = [r["user_id"] for r in conn.execute(
                    "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?", (g["id"],))]
                # weniger Teilnehmer als Gewinner → alle gewinnen
                winners = random.SystemRandom().sample(entries, min(len(entries), g["winner_count"]))
                for uid in winners:
                    conn.execute("UPDATE giveaway_entries SET is_winner = 1 WHERE giveaway_id = ? AND user_id = ?",
                                 (g["id"], uid))
                    coins.book(conn, uid, g["coins_per_winner"], "gewinnspiel", note=g["title"],
                               ref_type="giveaway", ref_id=g["id"])
                    db.notify(conn, uid, "giveaway_won",
                              f"🎉 Du hast beim Gewinnspiel „{g['title']}“ {g['coins_per_winner']} Coins gewonnen!")
                conn.execute("UPDATE giveaways SET drawn_at = datetime('now') WHERE id = ?", (g["id"],))
    finally:
        conn.close()


# ---------- Ende von RAM-Aktionen ----------

def end_ram_promotions(w) -> None:
    conn = w.conn()
    try:
        for s in conn.execute("""SELECT * FROM servers WHERE extra_ram_gb > 0 AND extra_ram_until <= ?
                                 AND state != 'deleted'""", (now_sql(),)).fetchall():
            conn.execute("UPDATE servers SET extra_ram_gb = 0, extra_ram_until = NULL, needs_restart = 1 WHERE id = ?",
                         (s["id"],))
            if s["state"] == "active":
                db.notify(conn, s["owner_id"], "ram_promo_end",
                          f"Die RAM-Aktion für „{s['name']}“ ist vorbei. Nach dem nächsten Neustart hat er wieder den normalen RAM.",
                          s["id"])
    finally:
        conn.close()


# ---------- „Benachrichtige mich, wenn Platz frei ist" ----------

def notify_waitlist(w) -> None:
    conn = w.conn()
    try:
        # wer zuerst vorgemerkt ist, wird zuerst benachrichtigt (eine Meldung pro Modell und Minute)
        done_models = set()
        for row in conn.execute("SELECT * FROM waitlist WHERE notified_at IS NULL ORDER BY id").fetchall():
            if row["model_id"] in done_models:
                continue
            m = servers.model(conn, row["model_id"])
            if m and servers.availability(conn, m):
                conn.execute("UPDATE waitlist SET notified_at = datetime('now') WHERE id = ?", (row["id"],))
                db.notify(conn, row["user_id"], "space_free",
                          f"Es ist wieder Platz für einen {m['name']}-Server frei – jetzt kaufen!")
                done_models.add(row["model_id"])
    finally:
        conn.close()


# ---------- Backups (nachts, Schnecken-Tempo) ----------

def nightly_backups(w) -> None:
    """Ab 02:00 jeden aktiven Server einmal pro Tag sichern, einen nach dem anderen.
    Wird alle 10 Minuten aufgerufen – holt Verpasstes nach (z. B. nach Stromausfall)."""
    local = datetime.now(ZoneInfo(config.TIMEZONE))
    if local.hour < 2:
        return
    day_start = fmt(local.replace(hour=2, minute=0, second=0, microsecond=0))
    conn = w.conn()
    try:
        todo = conn.execute(
            """SELECT * FROM servers s WHERE state = 'active' AND NOT EXISTS (
                 SELECT 1 FROM backups b WHERE b.server_id = s.id AND b.kind = 'taeglich' AND b.created_at >= ?)
               AND NOT EXISTS (SELECT 1 FROM jobs j WHERE j.server_id = s.id AND j.status IN ('pending', 'running'))
               ORDER BY id""", (day_start,)).fetchall()
        for server in todo:
            try:
                w.backup(conn, server, "taeglich")
            except Exception:
                log.exception("Backup für Server %s fehlgeschlagen", server["id"])
    finally:
        conn.close()


def cleanup_backups(w) -> None:
    """Älter als 7 Tage → löschen, wenn neuere existieren und nicht angepinnt."""
    conn = w.conn()
    try:
        old = conn.execute(
            """SELECT * FROM backups b WHERE pinned = 0 AND created_at < datetime('now', '-7 days')
               AND EXISTS (SELECT 1 FROM backups n WHERE n.server_id = b.server_id AND n.status = 'fertig'
                           AND n.id > b.id)""").fetchall()
        for b in old:
            shutil.rmtree(minecraft.backup_dir(b["server_id"]) / b["folder"], ignore_errors=True)
            conn.execute("DELETE FROM backups WHERE id = ?", (b["id"],))
    finally:
        conn.close()


def backup_database() -> None:
    """Tägliche Kopie der Datenbank (30 Tage behalten)."""
    target_dir = config.DATA_DIR / "db-backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"hostly-{time.strftime('%Y-%m-%d')}.sqlite"
    src = db.connect()
    try:
        dst = sqlite3.connect(target)
        src.backup(dst)
        dst.close()
    finally:
        src.close()
    limit = time.time() - 30 * 86400
    for f in target_dir.glob("hostly-*.sqlite"):
        if f.stat().st_mtime < limit:
            f.unlink(missing_ok=True)


def disk_usage(w) -> None:
    """Größe von Backups/Archiven/Servern – einmal täglich, nicht live (spart Last)."""
    conn = w.conn()
    try:
        for key, path in (("size_backups", config.DATA_DIR / "backups"), ("size_archives", config.ARCHIVES_DIR),
                          ("size_servers", config.SERVERS_DIR)):
            db.set_setting(conn, key, str(files.dir_size(path)))
        db.set_setting(conn, "size_checked_at", now_sql())
    finally:
        conn.close()
