"""Passwörter (Argon2id), Sitzungen, Login-Sperre und Eingabe-Regeln."""
import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from . import config

_hasher = PasswordHasher()  # Standard von argon2-cffi = Argon2id

# Ein fester Dummy-Hash, damit ein unbekannter Benutzername genauso lange dauert
# wie ein falsches Passwort (verrät nicht, ob es den Namen gibt).
_DUMMY_HASH = _hasher.hash("hostly-dummy-password")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


# ---------- Passwörter ----------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def random_password(length: int = 14) -> str:
    """Zufälliges Passwort (für Passwort-Zurücksetzen durch den Admin)."""
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------- Eingabe-Regeln (liefern einen Fehler-Schlüssel oder None) ----------

def check_username(username: str) -> str | None:
    if not (config.USERNAME_MIN <= len(username) <= config.USERNAME_MAX):
        return "err.username_length"
    if not USERNAME_RE.match(username):
        return "err.username_chars"
    return None


def check_password(password: str, repeat: str | None = None) -> str | None:
    if len(password) < config.PASSWORD_MIN:
        return "err.password_short"
    if len(password) > config.PASSWORD_MAX:
        return "err.password_long"
    if repeat is not None and password != repeat:
        return "err.password_mismatch"
    return None


# ---------- Sitzungen ----------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def create_session(conn: sqlite3.Connection, user_id: int, ip: str | None, user_agent: str | None) -> str:
    """Neue Sitzung anlegen. Das Token geht ins Cookie, in der DB steht nur sein Hash."""
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(days=config.SESSION_DAYS)
    conn.execute(
        "INSERT INTO sessions (user_id, token_hash, expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?)",
        (user_id, _token_hash(token), _fmt(expires), ip, (user_agent or "")[:300]),
    )
    return token


def load_session(conn: sqlite3.Connection, token: str | None):
    """Liefert (Sitzung, User) oder (None, None)."""
    if not token:
        return None, None
    row = conn.execute(
        """SELECT s.id AS session_id, s.admin_view, s.last_seen, u.*
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > datetime('now') AND u.deleted_at IS NULL""",
        (_token_hash(token),),
    ).fetchone()
    if row is None:
        return None, None
    # "zuletzt gesehen" höchstens alle 10 Minuten schreiben (spart Festplatten-Zugriffe)
    last_seen = datetime.strptime(row["last_seen"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    if _now() - last_seen > timedelta(minutes=10):
        conn.execute("UPDATE sessions SET last_seen = datetime('now') WHERE id = ?", (row["session_id"],))
    return {"id": row["session_id"], "admin_view": bool(row["admin_view"])}, row


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def delete_other_sessions(conn: sqlite3.Connection, user_id: int, keep_session_id: int | None) -> None:
    """Nach Passwort-Änderung: alle anderen Geräte abmelden."""
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND id IS NOT ?", (user_id, keep_session_id))


def cleanup_sessions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
    conn.execute("DELETE FROM login_attempts WHERE created_at < datetime('now', '-1 day')")


# ---------- Login-Sperre ----------

def is_locked(conn: sqlite3.Connection, username: str, ip: str | None) -> bool:
    window = f"-{config.LOGIN_LOCK_MINUTES} minutes"
    fails_user = conn.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE username = ? AND success = 0 AND created_at > datetime('now', ?)",
        (username, window),
    ).fetchone()[0]
    if fails_user >= config.LOGIN_MAX_FAILS_USER:
        return True
    if ip:
        fails_ip = conn.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND success = 0 AND created_at > datetime('now', ?)",
            (ip, window),
        ).fetchone()[0]
        if fails_ip >= config.LOGIN_MAX_FAILS_IP:
            return True
    return False


def record_login(conn: sqlite3.Connection, username: str, ip: str | None, success: bool) -> None:
    conn.execute(
        "INSERT INTO login_attempts (username, ip, success) VALUES (?, ?, ?)",
        (username, ip, int(success)),
    )
    if success:
        # erfolgreicher Login setzt die Fehlversuche für diesen Namen zurück
        conn.execute("DELETE FROM login_attempts WHERE username = ? AND success = 0", (username,))


# ---------- CSRF (Schutz gegen gefälschte Formulare) ----------

def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def csrf_ok(cookie_value: str | None, form_value: str | None) -> bool:
    return bool(cookie_value) and bool(form_value) and secrets.compare_digest(cookie_value, form_value)
