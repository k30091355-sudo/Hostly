"""Befehle für den Besitzer (im Ubuntu-Fenster ausführen).

  docker compose exec web python -m hostly.cli admin <benutzername>
      → macht diesen Account zum Admin (es gibt genau einen Admin)

  docker compose exec web python -m hostly.cli passwort <benutzername>
      → erzeugt ein zufälliges neues Passwort (z. B. wenn du dein eigenes vergessen hast)
"""
import sys

from . import db, security


def make_admin(username: str) -> int:
    db.init_db()
    conn = db.connect()
    try:
        user = conn.execute(
            "SELECT id, username FROM users WHERE username = ? AND deleted_at IS NULL", (username,)
        ).fetchone()
        if user is None:
            print(f"Kein Account mit dem Namen „{username}“ gefunden. Erst auf der Website registrieren.")
            return 1
        with db.transaction(conn):
            # genau ein Admin: alle anderen verlieren die Rolle
            conn.execute("UPDATE users SET is_admin = 0 WHERE id != ?", (user["id"],))
            conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user["id"],))
            conn.execute("UPDATE sessions SET admin_view = 1 WHERE user_id = ?", (user["id"],))
            db.audit(conn, user["id"], "admin_set")
        print(f"„{user['username']}“ ist jetzt Admin. Seite im Browser neu laden.")
        return 0
    finally:
        conn.close()


def reset_password(username: str) -> int:
    db.init_db()
    conn = db.connect()
    try:
        user = conn.execute(
            "SELECT id, username FROM users WHERE username = ? AND deleted_at IS NULL", (username,)
        ).fetchone()
        if user is None:
            print(f"Kein Account mit dem Namen „{username}“ gefunden.")
            return 1
        password = security.random_password()
        with db.transaction(conn):
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?",
                (security.hash_password(password), user["id"]),
            )
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
            db.audit(conn, user["id"], "password_reset", "cli")
        print(f"Neues Passwort für „{user['username']}“: {password}")
        print("Beim nächsten Login muss ein eigenes Passwort gewählt werden.")
        return 0
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "admin":
        return make_admin(argv[1])
    if len(argv) == 2 and argv[0] == "passwort":
        return reset_password(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
