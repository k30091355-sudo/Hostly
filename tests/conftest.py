import re

import pytest
from fastapi.testclient import TestClient

from hostly import config, db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    for name in ("SERVERS_DIR", "ARCHIVES_DIR", "UPLOADS_DIR", "DOWNLOADS_DIR"):
        monkeypatch.setattr(config, name, tmp_path / name.lower())
    from hostly.web.app import app

    with TestClient(app) as c:
        yield c


def csrf_of(client, url="/login"):
    """Seite laden und das CSRF-Token aus dem Formular lesen."""
    html = client.get(url).text
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def register(client, username="steve", password="geheim123"):
    token = csrf_of(client, "/registrieren")
    return client.post("/registrieren", data={
        "username": username, "password": password, "password2": password, "csrf": token,
    }, follow_redirects=False)


def login(client, username="steve", password="geheim123"):
    token = csrf_of(client, "/login")
    return client.post("/login", data={"username": username, "password": password, "csrf": token},
                       follow_redirects=False)


def logout(client):
    token = csrf_of(client, "/")
    client.post("/abmelden", data={"csrf": token})


def conn():
    return db.connect()
