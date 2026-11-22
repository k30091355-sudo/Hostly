"""Statistiken pro Server (öffentlich über das Kürzel) + kleine SVG-Grafik."""
import sqlite3
from datetime import datetime, timedelta, timezone

from markupsafe import Markup

from .timeutil import FMT, fmt


def server_stats(conn: sqlite3.Connection, server_id: int) -> dict:
    since7 = fmt(datetime.now(timezone.utc) - timedelta(days=7))
    samples = conn.execute(
        "SELECT at, running, players FROM player_samples WHERE server_id = ? AND at >= ? ORDER BY at",
        (server_id, since7)).fetchall()
    uptime = round(100 * sum(s["running"] for s in samples) / len(samples)) if samples else None
    peak = max((s["players"] for s in samples), default=0)
    sessions = conn.execute(
        """SELECT minecraft_name, COUNT(*) AS joins,
                  SUM((julianday(COALESCE(left_at, datetime('now'))) - julianday(joined_at)) * 24 * 60) AS minutes
           FROM player_sessions WHERE server_id = ? GROUP BY minecraft_name ORDER BY minutes DESC LIMIT 10""",
        (server_id,)).fetchall()
    total_minutes = conn.execute(
        """SELECT COALESCE(SUM((julianday(COALESCE(left_at, datetime('now'))) - julianday(joined_at)) * 24 * 60), 0)
           FROM player_sessions WHERE server_id = ?""", (server_id,)).fetchone()[0]
    return {"samples": samples, "uptime": uptime, "peak": peak, "top": sessions,
            "total_hours": round(total_minutes / 60, 1)}


def chart(samples, hours: int, max_players: int) -> Markup:
    """Spieler-Verlauf als SVG (Balken pro Zeitabschnitt, Höchstwert)."""
    now = datetime.now(timezone.utc)
    buckets = 48 if hours <= 24 else 56
    size = timedelta(hours=hours) / buckets
    start = now - timedelta(hours=hours)
    values = [0] * buckets
    for s in samples:
        at = datetime.strptime(s["at"], FMT).replace(tzinfo=timezone.utc)
        if at < start:
            continue
        i = min(buckets - 1, int((at - start) / size))
        values[i] = max(values[i], s["players"])
    top = max(max_players, 1)
    w, h, bw = 560, 120, 560 / buckets
    bars = "".join(
        f'<rect x="{i * bw + 1:.1f}" y="{h - v / top * (h - 4):.1f}" width="{bw - 2:.1f}" height="{v / top * (h - 4):.1f}" rx="2"><title>{v}</title></rect>'
        for i, v in enumerate(values) if v)
    return Markup(
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Spieler-Verlauf">'
        f'<line x1="0" y1="{h - 0.5}" x2="{w}" y2="{h - 0.5}" class="axis"/>{bars}</svg>')
