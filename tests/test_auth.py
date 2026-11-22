from hostly import cli

from .conftest import conn, csrf_of, login, logout, register


def test_home_without_login(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Hostly" in r.text
    assert "Account erstellen" in r.text


def test_register_logs_in_and_hashes_password(client):
    r = register(client, onboarded=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/willkommen"           # Einführung (1.3.0)
    assert "Willkommen bei Hostly, steve" in client.get("/willkommen").text
    row = conn().execute("SELECT password_hash FROM users WHERE username='steve'").fetchone()
    assert row["password_hash"].startswith("$argon2id$")
    assert "geheim123" not in row["password_hash"]


def test_register_validation(client):
    assert register(client, username="ab").status_code == 400
    assert register(client, username="böse name").status_code == 400
    assert register(client, password="kurz").status_code == 400
    token = csrf_of(client, "/registrieren")
    r = client.post("/registrieren", data={"username": "alex", "password": "geheim123",
                                           "password2": "anders123", "csrf": token})
    assert "stimmen nicht überein" in r.text


def test_username_unique_case_insensitive(client):
    register(client, "Steve")
    logout(client)
    r = register(client, "steve")
    assert r.status_code == 400
    assert "schon vergeben" in r.text


def test_name_check(client):
    register(client, "Steve")
    assert "vergeben" in client.get("/registrieren/name-pruefen?username=STEVE").text
    assert "frei" in client.get("/registrieren/name-pruefen?username=alex").text


def test_login_logout(client):
    register(client)
    logout(client)
    assert client.get("/einstellungen", follow_redirects=False).status_code == 303
    assert login(client, password="falsch123").status_code == 400
    r = login(client)
    assert r.status_code == 303
    assert client.get("/einstellungen").status_code == 200


def test_login_redirects_to_next(client):
    r = client.get("/einstellungen", follow_redirects=False)
    assert r.headers["location"] == "/login?next=%2Feinstellungen"
    register(client)
    logout(client)
    token = csrf_of(client)
    r = client.post("/login", data={"username": "steve", "password": "geheim123", "csrf": token,
                                    "next": "/einstellungen"}, follow_redirects=False)
    assert r.headers["location"] == "/einstellungen"
    # keine Weiterleitung auf fremde Seiten
    logout(client)
    token = csrf_of(client)
    r = client.post("/login", data={"username": "steve", "password": "geheim123", "csrf": token,
                                    "next": "//boese.example"}, follow_redirects=False)
    assert r.headers["location"] == "/"


def test_no_login_lock_after_failed_attempts(client):
    """Keine Sperre bei vielen Fehlversuchen (Entscheidung des Besitzers)."""
    register(client)
    logout(client)
    for _ in range(10):
        assert login(client, password="falsch123").status_code == 400
    assert login(client).status_code == 303


def test_one_time_account_wipe_migration(client, monkeypatch):
    """Migration 5 löscht beim Update einmalig alle Accounts; Codes und Tunnel bleiben."""
    from hostly import db
    monkeypatch.setattr(db, "MIGRATIONS", db.MIGRATIONS[:6])   # spätere Migrationen sind schon gelaufen
    register(client, "alt")
    c = conn()
    c.execute("INSERT INTO codes (code, coins, max_uses, uses, created_by) VALUES ('aaaa-bbbb-cccc-dddd', 100, 5, 1, 1)")
    c.execute("INSERT INTO tunnels (name, public_address, internal_ip) VALUES ('A', 'a', '172.30.0.11')")
    c.execute("PRAGMA user_version = 4")
    db.init_db()
    assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert c.execute("SELECT uses, created_by FROM codes").fetchone()[:] == (0, None)
    assert c.execute("SELECT COUNT(*) FROM tunnels").fetchone()[0] == 1
    db.init_db()   # läuft nur einmal
    logout(client)
    register(client, "neu")
    assert c.execute("SELECT is_admin FROM users WHERE username = 'neu'").fetchone()[0] == 1


def test_csrf_required(client):
    r = client.post("/registrieren", data={"username": "steve", "password": "geheim123",
                                           "password2": "geheim123", "csrf": "falsch"})
    assert r.status_code == 400
    assert conn().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_session_token_stored_as_hash(client):
    register(client)
    token = client.cookies.get("hostly_session")
    row = conn().execute("SELECT token_hash FROM sessions").fetchone()
    assert token and row["token_hash"] != token


def test_cli_password_reset_forces_change(client):
    register(client)
    logout(client)
    import io
    import contextlib
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cli.main(["passwort", "steve"]) == 0
    new_pw = out.getvalue().split(": ")[1].split()[0]
    assert login(client).status_code == 400  # altes Passwort geht nicht mehr
    assert login(client, password=new_pw).status_code == 303
    # muss zuerst ein eigenes Passwort wählen
    r = client.get("/", follow_redirects=False)
    assert r.headers["location"] == "/einstellungen"
    token = csrf_of(client, "/einstellungen")
    client.post("/einstellungen/passwort", data={"old_password": new_pw, "new_password": "meinneues1",
                                                 "new_password2": "meinneues1", "csrf": token})
    assert client.get("/", follow_redirects=False).status_code == 200
