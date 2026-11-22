from hostly import cli

from .conftest import conn, csrf_of, login, logout, register


def test_change_password(client):
    register(client)
    token = csrf_of(client, "/einstellungen")
    r = client.post("/einstellungen/passwort", data={"old_password": "falsch", "new_password": "neuespw1",
                                                     "new_password2": "neuespw1", "csrf": token})
    assert r.status_code == 400
    r = client.post("/einstellungen/passwort", data={"old_password": "geheim123", "new_password": "neuespw1",
                                                     "new_password2": "neuespw1", "csrf": token})
    assert "Passwort geändert" in r.text
    logout(client)
    assert login(client).status_code == 400
    assert login(client, password="neuespw1").status_code == 303


def test_password_change_logs_out_other_devices(client):
    register(client)
    other = conn()
    assert other.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    logout(client)
    login(client)
    login(client)  # zweite Sitzung (anderes Gerät)
    assert other.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    token = csrf_of(client, "/einstellungen")
    client.post("/einstellungen/passwort", data={"old_password": "geheim123", "new_password": "neuespw1",
                                                 "new_password2": "neuespw1", "csrf": token})
    assert other.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_change_username(client):
    register(client, "alex")
    logout(client)
    register(client, "steve")
    token = csrf_of(client, "/einstellungen")
    r = client.post("/einstellungen/benutzername", data={"username": "ALEX", "password": "geheim123", "csrf": token})
    assert "schon vergeben" in r.text
    r = client.post("/einstellungen/benutzername", data={"username": "Steve_2", "password": "geheim123",
                                                         "csrf": token})
    assert "Benutzername geändert" in r.text
    logout(client)
    assert login(client, "steve_2").status_code == 303


def test_display_settings_and_language(client):
    register(client)
    token = csrf_of(client, "/einstellungen")
    client.post("/einstellungen/darstellung", data={"language": "en", "theme": "dark", "csrf": token})
    html = client.get("/einstellungen").text
    assert 'data-theme="dark"' in html
    assert "Settings" in html


def test_guest_theme_and_language_cookie(client):
    token = csrf_of(client, "/")
    client.post("/design", data={"theme": "light", "csrf": token})
    client.post("/sprache", data={"language": "en", "csrf": token})
    html = client.get("/").text
    assert 'data-theme="light"' in html
    assert "Create account" in html


def test_admin_area_and_toggle(client):
    register(client)
    assert client.get("/admin", follow_redirects=False).status_code == 303  # kein Admin
    assert cli.main(["admin", "steve"]) == 0
    r = client.get("/admin")
    assert r.status_code == 200 and "Admin-Bereich" in r.text and "steve" in r.text
    # zur User-Ansicht
    token = csrf_of(client, "/")
    client.post("/admin/ansicht", data={"back": "/admin", "csrf": token})
    assert client.get("/admin", follow_redirects=False).status_code == 303
    assert "Zur Admin-Ansicht" in client.get("/").text
    # zurück zur Admin-Ansicht
    client.post("/admin/ansicht", data={"back": "/", "csrf": token})
    assert client.get("/admin").status_code == 200


def test_only_one_admin(client):
    register(client, "alex")
    logout(client)
    register(client, "steve")
    cli.main(["admin", "alex"])
    cli.main(["admin", "steve"])
    admins = [r[0] for r in conn().execute("SELECT username FROM users WHERE is_admin = 1")]
    assert admins == ["steve"]


def test_404_page(client):
    r = client.get("/gibtsnicht")
    assert r.status_code == 404
    assert "gibt es nicht" in r.text
