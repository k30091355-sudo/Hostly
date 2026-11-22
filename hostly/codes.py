"""Gutschein-Codes: erzeugen, normalisieren, einlösen."""
import re
import secrets
import sqlite3

from . import coins, config
from .timeutil import now_sql


def generate() -> str:
    """Zufälliger Code im Format xxxx-xxxx-xxxx-xxxx."""
    raw = "".join(secrets.choice(config.CODE_ALPHABET) for _ in range(16))
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def normalize(text: str) -> str:
    """Groß-/Kleinschreibung, Leerzeichen und fehlende Bindestriche egal."""
    raw = re.sub(r"[^0-9a-z]", "", text.lower())
    if len(raw) != 16:
        return raw
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def status(code: sqlite3.Row) -> str:
    """aktiv / aufgebraucht / deaktiviert / abgelaufen"""
    if not code["active"]:
        return "deaktiviert"
    if code["expires_at"] and code["expires_at"] <= now_sql():
        return "abgelaufen"
    if code["uses"] >= code["max_uses"]:
        return "aufgebraucht"
    return "aktiv"


class RedeemError(Exception):
    def __init__(self, message: str):
        self.message = message


def redeem(conn: sqlite3.Connection, user_id: int, text: str) -> int:
    """Code einlösen. Liefert die Coins oder wirft RedeemError mit der Meldung.
    Muss innerhalb von db.transaction() laufen."""
    code = conn.execute("SELECT * FROM codes WHERE code = ?", (normalize(text),)).fetchone()
    if code is None:
        raise RedeemError("Code ungültig")
    if not code["active"]:
        raise RedeemError("Code deaktiviert")
    if code["expires_at"] and code["expires_at"] <= now_sql():
        raise RedeemError("Code abgelaufen")
    already = conn.execute(
        "SELECT 1 FROM code_redemptions WHERE code_id = ? AND user_id = ?", (code["id"], user_id)
    ).fetchone()
    if already:
        raise RedeemError("Code bereits eingelöst")
    if code["uses"] >= code["max_uses"]:
        raise RedeemError("Code aufgebraucht")

    # Zähler nur erhöhen, wenn noch Platz ist (sicher auch bei gleichzeitigen Klicks)
    cur = conn.execute("UPDATE codes SET uses = uses + 1 WHERE id = ? AND uses < max_uses", (code["id"],))
    if cur.rowcount != 1:
        raise RedeemError("Code aufgebraucht")
    try:
        conn.execute("INSERT INTO code_redemptions (code_id, user_id) VALUES (?, ?)", (code["id"], user_id))
    except sqlite3.IntegrityError:
        raise RedeemError("Code bereits eingelöst")
    coins.book(conn, user_id, code["coins"], "code", note=code["code"], ref_type="code", ref_id=code["id"])
    return code["coins"]
