"""Coins: Kontostand = Summe aller Buchungen im Ledger.

Alle Funktionen hier erwarten, dass sie INNERHALB von `db.transaction()` laufen,
damit Prüfung und Buchung zusammen passieren (kein Minus, keine doppelte Buchung).
"""
import sqlite3


class NotEnoughCoins(Exception):
    pass


def balance(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM coin_ledger WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def book(conn: sqlite3.Connection, user_id: int, amount: int, reason: str, note: str = "",
         ref_type: str | None = None, ref_id: int | None = None, created_by: int | None = None) -> int:
    """Eine Buchung (+ oder −). Abbuchungen nur, wenn genug Coins da sind."""
    if amount == 0:
        return 0
    if amount < 0 and balance(conn, user_id) + amount < 0:
        raise NotEnoughCoins()
    cur = conn.execute(
        """INSERT INTO coin_ledger (user_id, amount, reason, note, ref_type, ref_id, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, amount, reason, note, ref_type, ref_id, created_by),
    )
    return cur.lastrowid


# Anzeigenamen der Buchungsgründe (deutsch; englisch über die Übersetzung)
REASONS = {
    "code": "Code eingelöst",
    "kauf": "Server gemietet",
    "verlaengerung": "Server verlängert",
    "auto_verlaengerung": "Automatisch verlängert",
    "reaktivierung": "Server reaktiviert",
    "erstattung": "Rückerstattung",
    "admin": "Admin-Buchung",
    "upgrade": "Modell-Upgrade",
    "uebertragung": "Übertragung",
    "nachtpause": "Nachtpausen-Erstattung",
    "gewinnspiel": "Gewinnspiel gewonnen",
    "account_geloescht": "Account gelöscht",
}
