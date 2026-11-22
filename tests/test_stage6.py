"""Stufe 6: Gewinnspiele, Aktionen, Nachtpause, Up-/Downgrade, Übertragungen, Account löschen."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from hostly import coins, db, nightpause, servers
from hostly.timeutil import fmt
from hostly.worker import tasks
from hostly.worker.jobs import Worker

from .conftest import conn, csrf_of, login, logout, register
from .helpers import FakeOps, FakeRcon, buy, run_jobs, set_until, setup_shop

BERLIN = ZoneInfo("Europe/Berlin")


def make_worker():
    return Worker(FakeOps(), FakeRcon())


def test_giveaway_fewer_participants_all_win(client):
    register(client, "admin")
    token = csrf_of(client, "/admin/gewinnspiele")
    client.post("/admin/gewinnspiele", data={"title": "Test", "coins_per_winner": 500, "winner_count": 3,
                                             "days": 7, "csrf": token})
    assert "Test" in client.get("/").text            # groß auf der Startseite
    client.post("/gewinnspiele/1/teilnehmen", data={"csrf": token})
    client.post("/gewinnspiele/1/teilnehmen", data={"csrf": token})   # nur 1× pro Konto
    c = conn()
    assert c.execute("SELECT COUNT(*) FROM giveaway_entries").fetchone()[0] == 1
    c.execute("UPDATE giveaways SET ends_at = '2000-01-01 00:00:00'")
    tasks.draw_giveaways(make_worker())
    assert coins.balance(c, 1) == 500
    assert "gewonnen" in client.get("/").text
    assert "admin" in client.get("/gewinnspiele").text


def test_promotion_discount_and_ram(client):
    c = setup_shop(client)
    now = datetime.now(timezone.utc)
    c.execute("INSERT INTO promotions (kind, title, percent, model_ids, starts_at, ends_at) VALUES ('rabatt', 'Woche', 20, '3', ?, ?)",
              (fmt(now - timedelta(days=1)), fmt(now + timedelta(days=1))))
    c.execute("INSERT INTO promotions (kind, title, extra_ram_gb, model_ids, starts_at, ends_at) VALUES ('ram', 'RAM', 1, '2', ?, ?)",
              (fmt(now - timedelta(days=1)), fmt(now + timedelta(days=1))))
    assert "750 Coins" in client.get("/kaufen/preis?model_id=3&days=30").text   # 30 % + 20 %
    assert "Woche" in client.get("/").text
    buy(client, model_id=2)
    s = c.execute("SELECT * FROM servers").fetchone()
    assert s["extra_ram_gb"] == 1
    w = make_worker()
    run_jobs(w)
    assert w.ops.containers["hostly-mc-1"]["spec"]["env"]["MEMORY"] == "4096M"
    assert servers.capacity(c)["used"] == 4.5
    c.execute("UPDATE servers SET extra_ram_until = '2000-01-01 00:00:00'")
    tasks.end_ram_promotions(w)
    s = c.execute("SELECT * FROM servers").fetchone()
    assert s["extra_ram_gb"] == 0 and s["needs_restart"] == 1
    assert "RAM-Aktion" in client.get("/").text


def test_night_pause_math():
    assert nightpause.refund(1050, 30, 6, 30) == 3        # Beispiel aus dem Konzept
    assert nightpause.refund(1050, 30, 15, 70) == 2       # gedeckelt auf 75 − 70 = 5 %
    assert nightpause.check(23, 7) is None and nightpause.planned_hours(23, 7) == 8
    assert nightpause.check(1, 17) is not None            # 16 Stunden
    t = datetime(2026, 11, 22, 2, 30, tzinfo=BERLIN)
    s, e = nightpause.window_containing(t, 23, 7)
    assert s.hour == 23 and s.day == 21 and e.hour == 7 and e.day == 22
    assert nightpause.window_containing(datetime(2026, 11, 22, 12, tzinfo=BERLIN), 23, 7) is None
    # Zeitumstellung (Oktober): Nacht ist 1 Stunde länger
    s, e = nightpause.window_containing(datetime(2026, 10, 25, 4, tzinfo=BERLIN), 1, 8)
    assert nightpause.real_hours(s, e) == 8


def test_night_pause_flow(client):
    c = setup_shop(client)
    token = csrf_of(client, "/kaufen")
    client.post("/kaufen", data={"model_id": 3, "server_type": "PAPER", "days": 30, "name": "Nacht",
                                 "np_on": "1", "np_start": 1, "np_end": 7, "request_id": "n1", "csrf": token})
    w = make_worker()
    run_jobs(w)
    before = coins.balance(c, 1)
    t = datetime.now(BERLIN).replace(hour=2, minute=0, second=0, microsecond=0)
    tasks.night_pauses(w, t.astimezone(timezone.utc))
    run_jobs(w)
    assert not w.ops.containers["hostly-mc-1"]["running"]
    assert "Nachtpause" in client.get("/server").text
    log_row = c.execute("SELECT * FROM night_pause_log").fetchone()
    assert log_row["status"] == "laeuft"
    # Ende der Pause → Erstattung: 1050/30 = 35 × 6 % = 2,1 → 3
    tasks.night_pauses(w, t.astimezone(timezone.utc) + timedelta(hours=6))
    run_jobs(w)
    assert coins.balance(c, 1) == before + 3
    assert w.ops.containers["hostly-mc-1"]["running"]
    # nächste Nacht: User startet selbst → keine Erstattung
    t2 = (t + timedelta(days=1)).astimezone(timezone.utc)
    tasks.night_pauses(w, t2)
    run_jobs(w)
    token = csrf_of(client, "/server/1")
    client.post("/server/1/aktion", data={"action": "start", "csrf": token})
    assert c.execute("SELECT status FROM night_pause_log ORDER BY id DESC").fetchone()[0] == "unterbrochen"


def test_upgrade_downgrade(client):
    c = setup_shop(client, coins_amount=1000)
    buy(client, model_id=1, days=1)   # Holz, 1 Tag, 0 % Rabatt
    w = make_worker()
    run_jobs(w)
    set_until(1, timedelta(days=10, hours=3))
    token = csrf_of(client, "/server/1/miete")
    page = client.get("/server/1/miete").text
    assert "200 Coins" in page   # 10 × (30 − 10)
    before = coins.balance(c, 1)
    client.post("/server/1/modell", data={"model_id": 2, "csrf": token})
    assert coins.balance(c, 1) == before - 200
    run_jobs(w)
    assert w.ops.containers["hostly-mc-1"]["spec"]["env"]["MAX_PLAYERS"] == "7"
    client.post("/server/1/modell", data={"model_id": 1, "csrf": token})
    assert coins.balance(c, 1) == before - 200 + 200


def test_transfers_and_account_delete(client):
    c = setup_shop(client, coins_amount=500)
    buy(client, model_id=1, days=1)
    logout(client)
    register(client, "bob")
    logout(client)
    login(client, "admin")
    token = csrf_of(client, "/einstellungen")
    r = client.post("/einstellungen/coins-uebertragen", data={"username": "bob", "amount": 100, "password": "falsch", "csrf": token})
    assert r.status_code == 400
    client.post("/einstellungen/coins-uebertragen", data={"username": "bob", "amount": 100, "password": "geheim123", "csrf": token})
    assert coins.balance(c, 2) == 100
    client.post("/server/1/uebertragen", data={"username": "bob", "password": "geheim123", "csrf": token})
    assert c.execute("SELECT owner_id FROM servers").fetchone()[0] == 2
    logout(client)
    login(client, "bob")
    token = csrf_of(client, "/einstellungen")
    client.post("/einstellungen/account-loeschen", data={"password": "geheim123", "confirm": "1", "csrf": token})
    assert c.execute("SELECT state FROM servers").fetchone()[0] == "deleted"
    assert coins.balance(c, 2) == 0
    assert login(client, "bob").status_code == 400
    register(client, "bob")   # Name wieder frei
    assert c.execute("SELECT COUNT(*) FROM users WHERE username = 'bob' AND deleted_at IS NULL").fetchone()[0] == 1


def test_maintenance_blocks_users_not_admin(client):
    register(client, "admin")
    db.set_setting(conn(), "maintenance_mode", "1")
    assert "Wartungsmodus" in client.get("/").text
    token = csrf_of(client, "/code")
    assert client.post("/code", data={"code": "x", "csrf": token}).status_code == 400   # Admin darf
    logout(client)
    register(client, "bob")   # Registrieren ist ein POST → gesperrt
    assert conn().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_waitlist(client):
    c = setup_shop(client, tunnels=1)
    buy(client, model_id=1)
    token = csrf_of(client, "/kaufen")
    assert "Benachrichtige mich" in client.get("/kaufen").text
    client.post("/kaufen/vormerken", data={"model_id": 1, "csrf": token})
    w = make_worker()
    tasks.notify_waitlist(w)
    assert c.execute("SELECT notified_at FROM waitlist").fetchone()[0] is None
    c.execute("INSERT INTO tunnels (name, public_address, internal_ip) VALUES ('B', 'b', '172.30.0.40')")
    tasks.notify_waitlist(w)
    assert "wieder Platz" in client.get("/").text
