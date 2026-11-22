"""Server mieten, verlängern, reaktivieren, löschen – die Regeln aus KONZEPT.md 11, 12, 14, 17.

Die Funktionen hier ändern nur die Datenbank und tragen Aufträge für den worker ein.
Sie müssen INNERHALB von `db.transaction()` aufgerufen werden.
"""
import secrets
import sqlite3
from datetime import timedelta

from . import coins, config, db, nightpause, pricing, promotions
from .timeutil import fmt, full_days_left, now, now_sql, parse

# Zustände, die RAM und einen Tunnel belegen
ACTIVE_STATES = ("creating", "active", "reactivating", "archiving")
SHORT_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"


class ServerError(Exception):
    def __init__(self, message: str):
        self.message = message


# ---------- Modelle & Aktionen ----------

def models(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM models ORDER BY sort").fetchall()


def model(conn: sqlite3.Connection, model_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()


def promo_percent(conn: sqlite3.Connection, model_id: int) -> int:
    """Summe aktiver Rabatt-Aktionen für dieses Modell."""
    return promotions.discount_percent(conn, model_id)


def effective_ram(server: sqlite3.Row, model_row: sqlite3.Row) -> float:
    """Modell-RAM + Extra-RAM aus einer RAM-Aktion (nur solange die Aktion läuft)."""
    extra = server["extra_ram_gb"] if server["extra_ram_until"] and server["extra_ram_until"] > now_sql() else 0
    return model_row["ram_gb"] + extra


def price_for(conn: sqlite3.Connection, model_row: sqlite3.Row, days: int) -> pricing.Price:
    return pricing.rent_price(days, model_row["price_per_day"], promo_percent(conn, model_row["id"]))


# ---------- Kapazität: RAM + Tunnel ----------

def ram_settings(conn: sqlite3.Connection) -> tuple[float, float]:
    total = float(db.get_setting(conn, "ram_total_gb", str(config.DEFAULT_RAM_TOTAL_GB)))
    reserve = float(db.get_setting(conn, "ram_reserve_gb", str(config.DEFAULT_RAM_RESERVE_GB)))
    return total, reserve


def container_limit_gb(model_row: sqlite3.Row) -> float:
    return model_row["ram_gb"] + config.CONTAINER_EXTRA_GB


def capacity(conn: sqlite3.Connection, exclude_server_id: int | None = None) -> dict:
    total, reserve = ram_settings(conn)
    used = conn.execute(
        f"""SELECT COALESCE(SUM(m.ram_gb + ? + CASE WHEN s.extra_ram_until > ? THEN s.extra_ram_gb ELSE 0 END), 0)
            FROM servers s JOIN models m ON m.id = s.model_id
            WHERE s.state IN ({','.join('?' * len(ACTIVE_STATES))}) AND s.id IS NOT ?""",
        (config.CONTAINER_EXTRA_GB, now_sql(), *ACTIVE_STATES, exclude_server_id),
    ).fetchone()[0]
    tunnels_total = conn.execute("SELECT COUNT(*) FROM tunnels WHERE active = 1").fetchone()[0]
    tunnels_used = conn.execute(
        "SELECT COUNT(*) FROM servers WHERE tunnel_id IS NOT NULL"
    ).fetchone()[0]
    return {"total": total, "reserve": reserve, "used": used, "free": total - used,
            "tunnels_total": tunnels_total, "tunnels_used": tunnels_used}


def free_tunnel(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM tunnels WHERE active = 1
           AND id NOT IN (SELECT tunnel_id FROM servers WHERE tunnel_id IS NOT NULL)
           ORDER BY id LIMIT 1"""
    ).fetchone()


def ram_ok(conn: sqlite3.Connection, model_row: sqlite3.Row, exclude_server_id: int | None = None,
           extra_gb: float | None = None) -> bool:
    """Nach dem Kauf müssen noch mindestens `reserve` GB frei bleiben (RAM-Aktionen zählen mit)."""
    if extra_gb is None:
        extra_gb = promotions.ram_bonus(conn, model_row["id"])[0]
    cap = capacity(conn, exclude_server_id)
    return cap["used"] + container_limit_gb(model_row) + extra_gb <= cap["total"] - cap["reserve"] + 1e-9


def availability(conn: sqlite3.Connection, model_row: sqlite3.Row) -> bool:
    return ram_ok(conn, model_row) and free_tunnel(conn) is not None


# ---------- Hilfen ----------

def _new_short_code(conn: sqlite3.Connection) -> str:
    while True:
        code = "".join(secrets.choice(SHORT_ALPHABET) for _ in range(6))
        if not conn.execute("SELECT 1 FROM servers WHERE short_code = ?", (code,)).fetchone():
            return code


def check_name(name: str) -> str | None:
    if not (1 <= len(name) <= 32):
        return "Der Name muss 1–32 Zeichen lang sein."
    if any(ord(c) < 32 for c in name):
        return "Der Name enthält ungültige Zeichen."
    return None


def check_days(days: int) -> str | None:
    if days < 1 or days > 3650:
        return "Bitte zwischen 1 und 3650 Tagen wählen."
    return None


def _check_request(conn: sqlite3.Connection, request_id: str | None) -> None:
    """Doppelklick-Schutz: jede Kauf-Seite hat eine einmalige Kennung."""
    if request_id and conn.execute("SELECT 1 FROM server_rentals WHERE request_id = ?", (request_id,)).fetchone():
        raise ServerError("Dieser Kauf wurde bereits ausgeführt.")


# ---------- Kaufen ----------

def purchase(conn: sqlite3.Connection, user_id: int, model_id: int, server_type: str, days: int,
             name: str, request_id: str | None = None, night_pause: tuple[int, int] | None = None,
             public_listed: bool = False, template: str | None = None, mc_version: str = "LATEST") -> int:
    m = model(conn, model_id)
    if m is None or server_type not in config.SERVER_TYPES:
        raise ServerError("Ungültige Auswahl.")
    err = check_days(days) or check_name(name) or (nightpause.check(*night_pause) if night_pause else None)
    if err:
        raise ServerError(err)
    _check_request(conn, request_id)

    price = price_for(conn, m, days)
    if coins.balance(conn, user_id) < price.final:
        raise ServerError("Nicht genug Coins.")
    tunnel = free_tunnel(conn)
    if tunnel is None or not ram_ok(conn, m):
        raise ServerError("Kauf aktuell nicht möglich – gerade ist kein Platz frei. Bitte später erneut versuchen.")

    until = now() + timedelta(days=days)
    extra_gb, extra_until = promotions.ram_bonus(conn, m["id"])
    cur = conn.execute(
        """INSERT INTO servers (owner_id, name, short_code, model_id, type, mc_version, state, tunnel_id, rented_until,
                                paid_total, paid_days, discount_percent, rcon_password, motd,
                                extra_ram_gb, extra_ram_until, night_pause_start, night_pause_end,
                                public_listed, template)
           VALUES (?, ?, ?, ?, ?, ?, 'creating', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, _new_short_code(conn), m["id"], server_type, mc_version, tunnel["id"], fmt(until),
         price.final, days, price.discount, secrets.token_urlsafe(24), name,
         extra_gb, extra_until, night_pause[0] if night_pause else None, night_pause[1] if night_pause else None,
         int(public_listed), template),
    )
    server_id = cur.lastrowid
    conn.execute(
        "INSERT INTO server_rentals (server_id, kind, days, price, discount_percent, request_id) VALUES (?, 'kauf', ?, ?, ?, ?)",
        (server_id, days, price.final, price.discount, request_id),
    )
    coins.book(conn, user_id, -price.final, "kauf", note=f"{name} · {m['name']} · {days} Tage",
               ref_type="server", ref_id=server_id)
    db.add_job(conn, "create", server_id, user_id)
    db.audit(conn, user_id, "server_bought", f"#{server_id} {m['name']} {days} Tage {price.final} Coins")
    return server_id


# ---------- Verlängern ----------

def extend(conn: sqlite3.Connection, server: sqlite3.Row, days: int, user_id: int,
           kind: str = "verlaengerung", request_id: str | None = None) -> pricing.Price:
    if server["state"] not in ("active", "creating"):
        raise ServerError("Dieser Server kann gerade nicht verlängert werden.")
    err = check_days(days)
    if err:
        raise ServerError(err)
    _check_request(conn, request_id)
    m = model(conn, server["model_id"])
    price = price_for(conn, m, days)
    try:
        coins.book(conn, server["owner_id"], -price.final, kind,
                   note=f"{server['name']} · {days} Tage", ref_type="server", ref_id=server["id"],
                   created_by=user_id)
    except coins.NotEnoughCoins:
        raise ServerError("Nicht genug Coins.")
    start = max(parse(server["rented_until"]), now())
    conn.execute(
        """UPDATE servers SET rented_until = ?, paid_total = paid_total + ?, paid_days = paid_days + ?,
                              warned_at = NULL WHERE id = ?""",
        (fmt(start + timedelta(days=days)), price.final, days, server["id"]),
    )
    conn.execute(
        "INSERT INTO server_rentals (server_id, kind, days, price, discount_percent, request_id) VALUES (?, ?, ?, ?, ?, ?)",
        (server["id"], kind, days, price.final, price.discount, request_id),
    )
    return price


def try_auto_renew(conn: sqlite3.Connection, server: sqlite3.Row) -> bool:
    """Am Ablauftag: immer 7 Tage, Rabatte gelten. False = zu wenig Coins."""
    try:
        extend(conn, server, 7, server["owner_id"], kind="auto_verlaengerung")
        return True
    except ServerError:
        return False


# ---------- Reaktivieren ----------

def reactivate(conn: sqlite3.Connection, server: sqlite3.Row, days: int, user_id: int,
               request_id: str | None = None) -> pricing.Price:
    if server["state"] != "archived":
        raise ServerError("Nur archivierte Server können reaktiviert werden.")
    err = check_days(days)
    if err:
        raise ServerError(err)
    _check_request(conn, request_id)
    m = model(conn, server["model_id"])
    price = price_for(conn, m, days)
    if coins.balance(conn, server["owner_id"]) < price.final:
        raise ServerError("Nicht genug Coins.")
    tunnel = free_tunnel(conn)
    if tunnel is None or not ram_ok(conn, m, exclude_server_id=server["id"]):
        raise ServerError("Aktuell nicht möglich – gerade ist kein Platz frei. Bitte später erneut versuchen.")
    coins.book(conn, server["owner_id"], -price.final, "reaktivierung",
               note=f"{server['name']} · {days} Tage", ref_type="server", ref_id=server["id"], created_by=user_id)
    conn.execute(
        """UPDATE servers SET state = 'reactivating', tunnel_id = ?, rented_until = ?, paid_total = ?,
                              paid_days = ?, discount_percent = ?, warned_at = NULL, archived_at = NULL
           WHERE id = ?""",
        (tunnel["id"], fmt(now() + timedelta(days=days)), price.final, days, price.discount, server["id"]),
    )
    conn.execute(
        "INSERT INTO server_rentals (server_id, kind, days, price, discount_percent, request_id) VALUES (?, 'reaktivierung', ?, ?, ?, ?)",
        (server["id"], days, price.final, price.discount, request_id),
    )
    db.add_job(conn, "reactivate", server["id"], user_id)
    return price


# ---------- Löschen ----------

def refund_amount(server: sqlite3.Row) -> int:
    if server["state"] not in ACTIVE_STATES:
        return 0
    return pricing.refund(full_days_left(server["rented_until"]), server["paid_total"], server["paid_days"])


def delete(conn: sqlite3.Connection, server: sqlite3.Row, by_user_id: int, with_refund: bool = True) -> int:
    if server["state"] == "deleted":
        raise ServerError("Der Server ist schon gelöscht.")
    amount = refund_amount(server) if with_refund else 0
    if amount > 0:
        coins.book(conn, server["owner_id"], amount, "erstattung", note=f"{server['name']} gelöscht",
                   ref_type="server", ref_id=server["id"], created_by=by_user_id)
    conn.execute(
        "UPDATE servers SET state = 'deleted', tunnel_id = NULL, deleted_at = datetime('now') WHERE id = ?",
        (server["id"],),
    )
    db.add_job(conn, "delete", server["id"], by_user_id)
    db.audit(conn, by_user_id, "server_deleted", f"#{server['id']} {server['name']} Erstattung {amount}")
    return amount


# ---------- Archivieren (vom worker beim Ablauf benutzt) ----------

def mark_archived(conn: sqlite3.Connection, server_id: int) -> None:
    conn.execute(
        "UPDATE servers SET state = 'archived', tunnel_id = NULL, archived_at = datetime('now') WHERE id = ?",
        (server_id,),
    )
    conn.execute("DELETE FROM server_status WHERE server_id = ?", (server_id,))


# ---------- Anzeige ----------

def display_status(server: sqlite3.Row, status: sqlite3.Row | None, night_paused: bool = False) -> tuple[str, str]:
    """(Text, CSS-Klasse) für die Anzeige."""
    state = server["state"]
    if state == "active" and server["crash_locked"]:
        return "abgestürzt", "crash"
    if state == "active" and night_paused and (status is None or not status["running"]):
        return "Nachtpause", "sleep"
    if state == "creating":
        return "wird erstellt …", "busy"
    if state == "reactivating":
        return "wird reaktiviert …", "busy"
    if state == "archiving":
        return "wird archiviert …", "busy"
    if state == "archived":
        return "archiviert", "off"
    if state == "deleted":
        return "gelöscht", "off"
    if status is None or not status["running"]:
        return "aus", "off"
    if status["paused"]:
        return "schläft", "sleep"
    if status["health"] == "starting":
        return "startet …", "busy"
    return f"online {status['players_online']}/{status['players_max']}", "on"


def can_manage(user: sqlite3.Row | None, is_admin: bool, server: sqlite3.Row) -> bool:
    return user is not None and (server["owner_id"] == user["id"] or is_admin)


# ---------- Upgrade / Downgrade (KONZEPT.md 12.7, 12.8) ----------

def change_model_price(server: sqlite3.Row, old: sqlite3.Row, new: sqlite3.Row) -> int:
    """Positiv = Upgrade-Preis, negativ = Downgrade-Erstattung (beides abgerundet)."""
    rest = full_days_left(server["rented_until"])
    diff = abs(new["price_per_day"] - old["price_per_day"])
    amount = rest * diff * (100 - server["discount_percent"]) // 100
    return amount if new["price_per_day"] > old["price_per_day"] else -amount


def change_model(conn: sqlite3.Connection, server: sqlite3.Row, new_model_id: int, user_id: int) -> int:
    if server["state"] != "active":
        raise ServerError("Nur aktive Server können das Modell wechseln.")
    old, new = model(conn, server["model_id"]), model(conn, new_model_id)
    if new is None or new["id"] == old["id"]:
        raise ServerError("Bitte ein anderes Modell wählen.")
    amount = change_model_price(server, old, new)
    if amount > 0:
        if not ram_ok(conn, new, exclude_server_id=server["id"], extra_gb=0):
            raise ServerError("Upgrade aktuell nicht möglich – gerade ist nicht genug RAM frei.")
        try:
            coins.book(conn, server["owner_id"], -amount, "upgrade", note=f"{server['name']} · {old['name']} → {new['name']}",
                       ref_type="server", ref_id=server["id"], created_by=user_id)
        except coins.NotEnoughCoins:
            raise ServerError("Nicht genug Coins.")
    elif amount < 0:
        coins.book(conn, server["owner_id"], -amount, "erstattung", note=f"{server['name']} · {old['name']} → {new['name']}",
                   ref_type="server", ref_id=server["id"], created_by=user_id)
    conn.execute(
        """UPDATE servers SET model_id = ?, paid_total = MAX(0, paid_total + ?), extra_ram_gb = 0,
                              extra_ram_until = NULL WHERE id = ?""",
        (new["id"], amount, server["id"]),
    )
    conn.execute(
        "INSERT INTO server_rentals (server_id, kind, days, price, discount_percent) VALUES (?, ?, ?, ?, ?)",
        (server["id"], "upgrade" if amount >= 0 else "downgrade", full_days_left(server["rented_until"]),
         amount, server["discount_percent"]),
    )
    db.add_job(conn, "restart", server["id"], user_id)
    return amount


# ---------- Übertragen (KONZEPT.md 18) ----------

def find_user(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE username = ? AND deleted_at IS NULL", (username.strip(),)).fetchone()


def transfer_coins(conn: sqlite3.Connection, from_id: int, to_username: str, amount: int) -> sqlite3.Row:
    to = find_user(conn, to_username)
    if to is None:
        raise ServerError("Diesen Benutzer gibt es nicht.")
    if to["id"] == from_id:
        raise ServerError("Du kannst dir nicht selbst Coins schicken.")
    if amount < 1:
        raise ServerError("Bitte einen Betrag ab 1 Coin eingeben.")
    sender = conn.execute("SELECT username FROM users WHERE id = ?", (from_id,)).fetchone()
    try:
        coins.book(conn, from_id, -amount, "uebertragung", note=f"an {to['username']}", ref_type="user", ref_id=to["id"])
    except coins.NotEnoughCoins:
        raise ServerError("Nicht genug Coins.")
    coins.book(conn, to["id"], amount, "uebertragung", note=f"von {sender['username']}", ref_type="user", ref_id=from_id)
    db.notify(conn, to["id"], "transfer", f"{sender['username']} hat dir {amount} Coins geschickt.")
    db.audit(conn, from_id, "coins_transferred", f"{amount} an {to['username']}")
    return to


def transfer_server(conn: sqlite3.Connection, server: sqlite3.Row, from_id: int, to_username: str) -> sqlite3.Row:
    to = find_user(conn, to_username)
    if to is None:
        raise ServerError("Diesen Benutzer gibt es nicht.")
    if to["id"] == server["owner_id"]:
        raise ServerError("Der Server gehört diesem Benutzer schon.")
    conn.execute("UPDATE servers SET owner_id = ? WHERE id = ?", (to["id"], server["id"]))
    if to["minecraft_name"] and server["state"] == "active":
        db.add_job(conn, "rcon", server["id"], from_id, {"commands": [f"op {to['minecraft_name']}"]})
    db.notify(conn, to["id"], "transfer", f"Dir wurde der Server „{server['name']}“ übertragen.", server["id"])
    db.audit(conn, from_id, "server_transferred", f"#{server['id']} an {to['username']}")
    return to


def night_pause_running(conn: sqlite3.Connection, server_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM night_pause_log WHERE server_id = ? AND status = 'laeuft'", (server_id,)).fetchone()
