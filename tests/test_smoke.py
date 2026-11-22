"""Jede Seite einmal öffnen (findet Fehler in Vorlagen)."""
from hostly.worker.jobs import Worker

from .conftest import conn, logout
from .helpers import FakeOps, FakeRcon, buy, run_jobs, setup_shop

PAGES = ["/", "/kaufen", "/code", "/einstellungen", "/einstellungen/coins", "/gewinnspiele", "/serverliste",
         "/statistik", "/server", "/server/1", "/server/1/konsole", "/server/1/darstellung", "/server/1/spieler",
         "/server/1/miete", "/server/1/erweiterungen", "/server/1/welten", "/server/1/dateien", "/server/1/backups",
         "/server/1/statistik", "/admin", "/admin/user", "/admin/user/1", "/admin/server", "/admin/codes",
         "/admin/tunnel", "/admin/einstellungen", "/admin/gewinnspiele", "/admin/aktionen", "/admin/backups"]


def test_all_pages_render(client):
    c = setup_shop(client)
    buy(client)
    buy(client, name="Zweiter", request_id="r2")
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    c.execute("UPDATE servers SET mc_version = '1.21.4'")
    for url in PAGES:
        r = client.get(url)
        assert r.status_code == 200, url
    c.execute("UPDATE servers SET state = 'archived', tunnel_id = NULL WHERE id = 2")
    for url in ("/server/2", "/server/2/miete", "/server/2/statistik", "/server", "/admin/backups"):
        assert client.get(url).status_code == 200, url
    code = c.execute("SELECT short_code FROM servers WHERE id = 1").fetchone()[0]
    assert client.get(f"/s/{code}").status_code == 200
    # englisch
    c.execute("UPDATE users SET language = 'en', theme = 'dark'")
    for url in PAGES:
        assert client.get(url).status_code == 200, url
    logout(client)
    for url in ("/", "/kaufen", "/gewinnspiele", "/serverliste", "/statistik", "/login", "/registrieren"):
        assert client.get(url).status_code == 200, url
