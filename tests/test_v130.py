"""Version 1.3.0: Einstellungen, Gamerules, neue Welt, Mod-Updates, Fehler-Erklärer, Leistung,
Whitelist-Anfragen, Startbonus, Einführung, Admin-Werte, geplante Wartung."""
import json

from hostly import gamesettings, minecraft
from hostly.worker.jobs import Worker

from .conftest import conn, csrf_of
from .helpers import FakeOps, FakeRcon, buy, run_jobs, setup_shop


def active_server(client):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    return c, w


def test_settings_saved_and_in_container_env(client):
    c, w = active_server(client)
    assert "Gamerules" in client.get("/server/1/einstellungen").text
    token = csrf_of(client, "/server/1/einstellungen")
    client.post("/server/1/einstellungen", data={"difficulty": "hard", "gamemode": "creative", "view_distance": "50",
                                                  "spawn_protection": "0", "allow_flight": "1", "csrf": token})
    s = c.execute("SELECT * FROM servers").fetchone()
    assert (s["difficulty"], s["gamemode"], s["view_distance"], s["pvp"], s["allow_flight"], s["needs_restart"]) == \
        ("hard", "creative", 12, 0, 1, 1)   # Sichtweite auf 12 begrenzt, PvP aus (Häkchen fehlt)
    assert json.loads(s["gamerules"])["pvp"] is False
    client.post("/server/1/aktion", data={"action": "restart", "csrf": token})
    run_jobs(w)
    env = w.ops.containers["hostly-mc-1"]["spec"]["env"]
    assert env["DIFFICULTY"] == "hard" and env["MODE"] == "creative" and env["VIEW_DISTANCE"] == "12"
    assert env["PVP"] == "FALSE" and env["ALLOW_FLIGHT"] == "TRUE" and env["SPAWN_PROTECTION"] == "0"


def test_gamerules_datapack_and_rcon(client):
    c, w = active_server(client)
    token = csrf_of(client, "/server/1/einstellungen")
    client.post("/server/1/gamerules", data={"keep_inventory": "1", "advance_time": "1",
                                              "players_sleeping_percentage": "30", "csrf": token})
    run_jobs(w)
    assert "gamerule keep_inventory true" in w.rcon.commands
    assert "gamerule keepInventory true" in w.rcon.commands          # ältere Versionen
    assert "gamerule spawn_mobs false" in w.rcon.commands
    assert "gamerule players_sleeping_percentage 30" in w.rcon.commands
    pack = minecraft.data_dir(1) / "world" / "datapacks" / "hostly-rules"
    assert "gamerule keep_inventory true" in (pack / "data/hostly_rules/function/new.mcfunction").read_text()
    tag = json.loads((pack / "data/minecraft/tags/function/load.json").read_text())
    assert all(v["required"] is False for v in tag["values"])        # unpassende Funktion stört nicht
    page = client.get("/server/1/einstellungen").text
    assert 'name="keep_inventory" value="1" checked' in page


def test_gamerule_commands_both_names():
    new, old = gamesettings.commands({"keep_inventory": True, "pvp": False})
    assert new == ["gamerule keep_inventory true", "gamerule pvp false"]
    assert old == ["gamerule keepInventory true"]


def test_new_world_backup_then_delete(client):
    c, w = active_server(client)
    data = minecraft.data_dir(1)
    for name in ("world", "world_nether", "world_the_end", "plugins"):
        (data / name).mkdir(parents=True, exist_ok=True)
        (data / name / "x.dat").write_text("x")
    token = csrf_of(client, "/server/1/einstellungen")
    r = client.post("/server/1/neue-welt", data={"seed": "123", "csrf": token})
    assert r.status_code == 400                                       # ohne Bestätigung nichts
    client.post("/server/1/neue-welt", data={"seed": "123", "confirm": "1", "csrf": token})
    run_jobs(w)
    assert not (data / "world" / "x.dat").exists() and not (data / "world_nether").exists()
    assert (data / "plugins" / "x.dat").exists()                       # Plugins bleiben
    assert c.execute("SELECT world_seed FROM servers").fetchone()[0] == "123"
    b = c.execute("SELECT kind, status FROM backups").fetchone()
    assert tuple(b) == ("vor-aenderung", "fertig")


REAL_FABRIC_LOG = """[18:56:13] [main/ERROR]: Incompatible mods found!
net.fabricmc.loader.impl.FormattedException: Some of your mods are incompatible with the game or each other!
More details:
	 - Mod 'TabTPS' (tabtps-fabric) 1.4.3 requires any version of mod 'Cloud' (cloud), which can't be loaded due to other constraints!
	 - Mod 'TabTPS' (tabtps-fabric) 1.4.3 requires any version of fabric-api, which is missing!
"""


def test_diagnose_real_fabric_api_log():
    from hostly import diagnose
    found = diagnose.analyse(REAL_FABRIC_LOG, "FABRIC")
    assert found[0].key == "fabric_api" and "TabTPS" in found[0].text
    assert all(f.key != "incompatible" for f in found)   # die genaue Ursache reicht


def test_diagnose_other_patterns():
    from hostly import diagnose
    log = ("Mod 'Sodium Extra' (sodium-extra) 1.0 requires version 0.6 or later of mod 'Sodium' (sodium), which is missing!\n"
           "java.lang.OutOfMemoryError: Java heap space\n"
           "[Server thread/WARN]: Unknown/missing dependency plugins: [Vault]. Please download and install these plugins\n"
           + "Can't keep up! Is the server overloaded? Running 5000ms or 100 ticks behind\n" * 3)
    keys = {f.key for f in diagnose.analyse(log)}
    assert {"missing:sodium", "memory", "dep:Vault", "lag"} <= keys


def test_diagnosis_shown_in_overview_with_button(client):
    c = setup_shop(client)
    buy(client, server_type="FABRIC")
    run_jobs(Worker(FakeOps(), FakeRcon()))
    logs = minecraft.data_dir(1) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "latest.log").write_text(REAL_FABRIC_LOG)
    page = client.get("/server/1").text
    assert "Hostly hat ein Problem erkannt" in page and "Fabric API jetzt hinzufügen" in page
    assert "Die Fabric API fehlt" in client.get("/server/1/konsole").text


def test_performance_values_recorded_and_shown(client):
    from hostly.worker import tasks
    c, w = active_server(client)
    w.ops.stats = lambda name: {"cpu_percent": 150.0, "mem_mb": 2048}
    real = w.rcon

    def rcon(host, port, pw, cmd, attempts=8):
        if cmd == "tick query":
            return ("The game is running normally\nTarget tick rate: 20.0 per second.\n"
                    "Average time per tick: 62.5ms (Target: 50.0ms)")
        return real(host, port, pw, cmd, attempts)
    w.rcon = rcon
    tasks.status_all(w)
    st = c.execute("SELECT cpu_percent, mem_mb, tps FROM server_status").fetchone()
    assert tuple(st) == (150.0, 2048, 16.0)
    assert c.execute("SELECT tps FROM player_samples").fetchone()[0] == 16.0
    page = client.get("/server/1/statistik").text
    assert "Leistung" in page and ">16.0<" in page and "2.0<small>" in page
    assert tasks.parse_tps("Average time per tick: 0.3ms") == 20.0


def test_whitelist_request_flow(client):
    from .conftest import logout, register, login
    c, w = active_server(client)
    token = csrf_of(client, "/server/1/spieler")
    client.post("/server/1/whitelist", data={"action": "on", "csrf": token})
    code = c.execute("SELECT short_code FROM servers").fetchone()[0]
    logout(client)
    assert "Zum Anfragen einloggen" in client.get(f"/s/{code}").text
    register(client, "bob")
    token = csrf_of(client, f"/s/{code}")
    client.post(f"/s/{code}/anfrage", data={"minecraft_name": "Bob_123", "message": "Hi!", "csrf": token})
    client.post(f"/s/{code}/anfrage", data={"minecraft_name": "Bob_123", "csrf": token})   # nur eine offene
    assert c.execute("SELECT COUNT(*) FROM whitelist_requests").fetchone()[0] == 1
    assert "wartet auf den Besitzer" in client.get(f"/s/{code}").text
    logout(client)
    login(client, "admin")
    page = client.get("/server/1/spieler").text
    assert "Whitelist-Anfragen (1)" in page and "Bob_123" in page and "Hi!" in page
    rid = c.execute("SELECT id FROM whitelist_requests").fetchone()[0]
    token = csrf_of(client, "/server/1/spieler")
    client.post(f"/server/1/anfrage/{rid}", data={"action": "accept", "csrf": token})
    assert c.execute("SELECT minecraft_name FROM whitelist").fetchone()[0] == "Bob_123"
    run_jobs(w)
    assert "whitelist add Bob_123" in w.rcon.commands
    bob = c.execute("SELECT id FROM users WHERE username = 'bob'").fetchone()[0]
    assert "angenommen" in c.execute("SELECT text FROM notifications WHERE user_id = ?", (bob,)).fetchone()[0]


def test_signup_bonus_promo_and_onboarding(client):
    from hostly import coins, db
    from .conftest import register
    c = conn()
    db.set_setting(c, "welcome_coins", "100")
    c.execute("""INSERT INTO promotions (kind, title, extra_coins, model_ids, starts_at, ends_at)
                 VALUES ('start', 'Willkommenswoche', 50, 'all', datetime('now', '-1 hour'), datetime('now', '+1 day'))""")
    assert "Endet in" in client.get("/").text and "data-countdown" in client.get("/").text
    r = register(client, "neu", onboarded=False)
    assert r.headers["location"] == "/willkommen"
    assert coins.balance(c, 1) == 150
    assert c.execute("SELECT reason FROM coin_ledger").fetchone()[0] == "startbonus"
    assert client.get("/", follow_redirects=False).headers["location"] == "/willkommen"   # bis überspringen
    page = client.get("/willkommen").text
    assert "150 Coins" in page and "Überspringen" in page
    token = csrf_of(client, "/willkommen")
    r = client.post("/willkommen", data={"next": "/kaufen", "csrf": token}, follow_redirects=False)
    assert r.headers["location"] == "/kaufen"
    assert client.get("/", follow_redirects=False).status_code == 200


def test_admin_welcome_coins_and_start_promo(client):
    from hostly import db
    c = setup_shop(client)
    token = csrf_of(client, "/admin/einstellungen")
    client.post("/admin/startcoins", data={"welcome_coins": "250", "csrf": token})
    assert db.get_setting(c, "welcome_coins") == "250"
    client.post("/admin/aktionen", data={"kind": "start", "title": "Bonus", "extra_coins": "40",
                                         "starts": "2026-01-01", "ends": "2099-01-01", "csrf": token})
    row = c.execute("SELECT kind, extra_coins, model_ids FROM promotions").fetchone()
    assert tuple(row) == ("start", 40, "all")
    assert "Start-Coins für neue Accounts" in client.get("/admin/aktionen").text


def test_coins_forecast_and_reminder(client):
    from hostly.worker import tasks
    from .helpers import set_until
    c, w = active_server(client)
    c.execute("UPDATE servers SET auto_renew = 1")
    page = client.get("/").text
    assert "Coins-Prognose" in page and "✓" in page
    c.execute("DELETE FROM coin_ledger")
    assert "es fehlen" in client.get("/").text
    set_until(1, __import__("datetime").timedelta(days=2))
    tasks.coins_reminder(w)
    tasks.coins_reminder(w)   # nur einmal
    assert c.execute("SELECT COUNT(*) FROM notifications WHERE kind = 'coins_low'").fetchone()[0] == 1


def test_planned_maintenance_countdown_and_auto_switch(client):
    from hostly import db
    from hostly.worker import tasks
    c, w = active_server(client)
    token = csrf_of(client, "/admin/einstellungen")
    client.post("/admin/wartung-planen", data={"start": "2099-01-01T03:00", "end": "2099-01-01T04:00",
                                               "action": "plan", "csrf": token})
    assert "Geplante Wartung in" in client.get("/").text
    c.execute("UPDATE settings SET value = datetime('now', '-1 minute') WHERE key = 'maintenance_planned_start'")
    tasks.planned_maintenance(w)
    assert db.get_setting(c, "maintenance_mode") == "1"
    c.execute("UPDATE settings SET value = datetime('now', '-1 minute') WHERE key = 'maintenance_auto_end'")
    tasks.planned_maintenance(w)
    assert db.get_setting(c, "maintenance_mode") == "0"


def test_host_samples_chart_and_warnings(client, monkeypatch):
    from hostly.worker import host
    c, w = active_server(client)
    host.cpu_percent()                      # erste Messung = Startwert
    host.sample(w)
    host.sample(w)
    row = c.execute("SELECT * FROM host_samples ORDER BY at DESC").fetchone()
    assert row["mem_total_mb"] and row["disk_total_gb"]
    assert "Mini-PC – letzte 7 Tage" in client.get("/admin").text
    # Warnungen: Festplatte voll + playit-Agent läuft nicht → einmal an Admins
    monkeypatch.setattr(host, "disk", lambda: (95.0, 100.0))
    host.sample(w)
    host.sample(w)
    kinds = [r[0] for r in c.execute("SELECT kind FROM notifications WHERE user_id = 1")]
    assert kinds.count("warn_disk") == 1 and kinds.count("warn_playit_1") == 1
    assert "Festplatte ist zu 95 % voll" in client.get("/admin").text
