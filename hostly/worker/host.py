"""Mini-PC-Werte (Version 1.3.0): alle 5 Minuten CPU, RAM, Festplatte, Temperatur speichern + Warnungen.

Liest nur /proc und /sys (billig, weckt keinen Minecraft-Server).
"""
import glob
import logging
import shutil

from .. import config, db
from ..timeutil import now_sql

log = logging.getLogger("hostly.worker")

_last_cpu: tuple[int, int] | None = None
DISK_WARN_PERCENT = 90
TEMP_WARN_C = 85


def _cpu_times() -> tuple[int, int] | None:
    try:
        with open("/proc/stat") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        return sum(parts), idle
    except (OSError, ValueError, IndexError):
        return None


def cpu_percent() -> float | None:
    """Durchschnitt seit der letzten Messung (also über ca. 5 Minuten)."""
    global _last_cpu
    now = _cpu_times()
    if now is None:
        return None
    prev, _last_cpu = _last_cpu, now
    if prev is None or now[0] <= prev[0]:
        return None
    total, idle = now[0] - prev[0], now[1] - prev[1]
    return round(100 * (total - idle) / total, 1)


def memory() -> tuple[int | None, int | None]:
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0]) // 1024
        return mem["MemTotal"] - mem["MemAvailable"], mem["MemTotal"]
    except (OSError, KeyError, ValueError):
        return None, None


def disk() -> tuple[float | None, float | None]:
    try:
        du = shutil.disk_usage(config.DATA_DIR if config.DATA_DIR.exists() else "/")
        return round(du.used / 1024 ** 3, 1), round(du.total / 1024 ** 3, 1)
    except OSError:
        return None, None


def temperature() -> float | None:
    """Höchste Temperatur der Sensoren. In WSL meist nicht verfügbar → None."""
    best = None
    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            with open(path) as f:
                value = int(f.read().strip()) / 1000
            if 0 < value < 150:
                best = value if best is None else max(best, value)
        except (OSError, ValueError):
            continue
    return round(best, 1) if best is not None else None


def sample(w) -> None:
    conn = w.conn()
    try:
        used, total = memory()
        d_used, d_total = disk()
        conn.execute(
            """INSERT INTO host_samples (at, cpu_percent, mem_used_mb, mem_total_mb, disk_used_gb, disk_total_gb, temp_c)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now_sql(), cpu_percent(), used, total, d_used, d_total, temperature()))
        conn.execute("DELETE FROM host_samples WHERE at < datetime('now', '-8 days')")
        check_warnings(w, conn)
    finally:
        conn.close()


def _warn_admins(conn, key: str, text: str, hours: int = 12) -> None:
    """Nachricht an alle Admins – dieselbe Warnung höchstens alle `hours` Stunden."""
    admins = [r[0] for r in conn.execute("SELECT id FROM users WHERE is_admin = 1")]
    for uid in admins:
        seen = conn.execute(
            "SELECT 1 FROM notifications WHERE user_id = ? AND kind = ? AND created_at > datetime('now', ?)",
            (uid, key, f"-{hours} hours")).fetchone()
        if not seen:
            db.notify(conn, uid, key, text)


def current_warnings(conn, ops=None) -> list[tuple[str, str]]:
    """(Schlüssel, Text) aller aktuellen Probleme – auch für das Admin-Dashboard."""
    out = []
    d_used, d_total = disk()
    if d_used and d_total and d_used / d_total * 100 >= DISK_WARN_PERCENT:
        out.append(("warn_disk", f"Die Festplatte ist zu {round(d_used / d_total * 100)} % voll "
                                 f"({round(d_total - d_used)} GB frei). Alte Archive/Backups löschen."))
    temp = temperature()
    if temp is not None and temp >= TEMP_WARN_C:
        out.append(("warn_temp", f"Der Mini-PC ist sehr warm ({temp:.0f} °C). Lüftung prüfen."))
    if ops is not None:
        accounts = {r[0] for r in conn.execute("SELECT DISTINCT playit_account FROM tunnels WHERE active = 1")}
        for acc in sorted(accounts):
            name = f"hostly-playit-{acc}"
            try:
                st = ops.state(name)
            except Exception:
                continue
            if not st.get("running"):
                out.append((f"warn_playit_{acc}",
                            f"Der playit-Agent {acc} läuft nicht – Spieler können sich nicht verbinden. "
                            f"Ubuntu: cd /srv/hostly/app && docker compose up -d"))
    return out


def check_warnings(w, conn) -> None:
    for key, text in current_warnings(conn, w.ops):
        _warn_admins(conn, key, text)
