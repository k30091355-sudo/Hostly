"""Rabatt-Aktionen und RAM-Aktionen (KONZEPT.md 12.2, 12.5)."""
import sqlite3

from .timeutil import now_sql


def active(conn: sqlite3.Connection, kind: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM promotions WHERE starts_at <= ? AND ends_at > ?"
    args: list = [now_sql(), now_sql()]
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    return conn.execute(sql + " ORDER BY ends_at", args).fetchall()


def applies(promo: sqlite3.Row, model_id: int) -> bool:
    ids = promo["model_ids"]
    return ids == "all" or str(model_id) in ids.split(",")


def discount_percent(conn: sqlite3.Connection, model_id: int) -> int:
    """Summe aller aktiven Rabatt-Aktionen für dieses Modell (Deckel 75 % kommt in pricing)."""
    return sum(p["percent"] for p in active(conn, "rabatt") if applies(p, model_id))


def signup_bonus(conn: sqlite3.Connection) -> int:
    """Start-Coins für neue Accounts: Grundwert (Admin-Einstellung) + laufende „Startbonus“-Aktionen."""
    from . import db
    try:
        base = max(0, int(db.get_setting(conn, "welcome_coins") or 0))
    except ValueError:
        base = 0
    return base + sum(p["extra_coins"] for p in active(conn, "start"))


def ram_bonus(conn: sqlite3.Connection, model_id: int) -> tuple[float, str | None]:
    """(Extra-RAM in GB, bis wann) – gilt nur für Mieten, die während der Aktion gekauft werden."""
    best = (0.0, None)
    for p in active(conn, "ram"):
        if applies(p, model_id) and p["extra_ram_gb"] > best[0]:
            best = (p["extra_ram_gb"], p["ends_at"])
    return best
