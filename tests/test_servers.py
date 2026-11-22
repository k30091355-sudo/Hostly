
from datetime import timedelta

from hostly import coins, minecraft
from hostly.worker import tasks
from hostly.worker.jobs import Worker

from .conftest import conn, csrf_of, logout, register
from .helpers import FakeOps, FakeRcon, buy, run_jobs, set_until, setup_shop


def make_worker():
    return Worker(FakeOps(), FakeRcon())


def test_shop_visible_without_login(client):
    r = client.get("/kaufen")
    assert r.status_code == 200 and "Holz" in r.text and "Zum Kaufen einloggen" in r.text
    r = client.get("/kaufen/preis?model_id=3&days=30")
    assert "1.050 Coins" in r.text and "−30 %" in r.text


def test_purchase_creates_server_and_job(client):
    c = setup_shop(client)
    r = buy(client, model_id=2, days=7)
    assert r.status_code == 303
    server = c.execute("SELECT * FROM servers").fetchone()
    assert server["state"] == "creating" and server["tunnel_id"] == 1
    assert coins.balance(c, 1) == 5000 - 195
    assert c.execute("SELECT kind FROM jobs").fetchone()[0] == "create"
    # Doppelklick: gleiche Kennung bucht nicht nochmal
    assert buy(client, request_id="r1").status_code == 400
    assert coins.balance(c, 1) == 5000 - 195


def test_purchase_checks_coins_ram_tunnel(client):
    c = setup_shop(client, coins_amount=100, tunnels=1)
    assert "Nicht genug Coins" in buy(client, model_id=3, days=7).text
    with c:
        pass
    from hostly import db
    with db.transaction(c):
        coins.book(c, 1, 100000, "admin")
    assert buy(client, model_id=1, request_id="a").status_code == 303
    r = buy(client, model_id=1, request_id="b")  # kein Tunnel mehr frei
    assert "Kauf aktuell nicht möglich" in r.text
    # RAM: 12 GB − 1,5 Reserve = 10,5 → 2× Diamant (9 GB) + Holz (2,5) passt nicht
    for i in range(5):
        c.execute("INSERT INTO tunnels (name, public_address, internal_ip) VALUES (?, ?, ?)",
                  (f"X{i}", f"x{i}", f"172.30.0.{50 + i}"))
    assert buy(client, model_id=3, request_id="c").status_code == 303   # 2,5 + 4,5 = 7
    r = buy(client, model_id=3, request_id="d")                          # + 4,5 = 11,5 > 10,5
    assert "Kauf aktuell nicht möglich" in r.text
    assert buy(client, model_id=1, request_id="e").status_code == 303   # + 2,5 = 9,5 ✓


def test_worker_creates_and_controls_server(client):
    c = setup_shop(client)
    buy(client)
    w = make_worker()
    run_jobs(w)
    server = c.execute("SELECT * FROM servers").fetchone()
    assert server["state"] == "active"
    spec = w.ops.containers["hostly-mc-1"]["spec"]
    assert spec["ip"] == "172.30.0.11"
    assert spec["env"]["MEMORY"] == "3072M" and spec["env"]["MAX_PLAYERS"] == "7"
    assert spec["env"]["TYPE"] == "PAPER" and spec["env"]["ENABLE_AUTOPAUSE"] == "TRUE"
    assert spec["mem_limit"] == int(3.5 * 1024 ** 3)
    st = c.execute("SELECT * FROM server_status").fetchone()
    assert st["running"] == 1 and st["players_online"] == 1 and st["players"] == "Steve"
    assert "online 1/7" in client.get("/server/1").text

    token = csrf_of(client, "/server/1")
    client.post("/server/1/aktion", data={"action": "stop", "csrf": token})
    run_jobs(w)
    assert "save-all" in w.rcon.commands
    assert not w.ops.containers["hostly-mc-1"]["running"]
    assert "offline" in client.get("/server/1").text


def test_paused_server_is_never_pinged(client):
    c = setup_shop(client)
    buy(client)
    w = make_worker()
    run_jobs(w)
    w.rcon.commands.clear()
    (minecraft.data_dir(1) / ".paused").touch()
    tasks.status_all(w)
    assert w.rcon.commands == []  # kein "list" → Server bleibt eingefroren
    assert c.execute("SELECT paused FROM server_status").fetchone()[0] == 1
    assert "schläft" in client.get("/server").text


def test_console(client):
    setup_shop(client)
    buy(client)
    w = make_worker()
    run_jobs(w)
    token = csrf_of(client, "/server/1/konsole")
    r = client.post("/server/1/konsole", data={"command": "minecraft:stop", "csrf": token})
    assert "gesperrt" in r.text
    client.post("/server/1/konsole", data={"command": "/say hallo", "csrf": token})
    run_jobs(w)
    assert "say hallo" in w.rcon.commands
    log = minecraft.data_dir(1) / "logs"
    log.mkdir(parents=True)
    (log / "latest.log").write_text("[10:00:00] [Server thread/INFO]: Done!\n")
    assert "Done!" in client.get("/server/1/konsole/log").text


def test_other_users_cannot_see_server(client):
    setup_shop(client)
    buy(client)
    logout(client)
    register(client, "bob")
    assert client.get("/server/1").status_code == 404


def test_extend_and_auto_renew_and_archive(client):
    c = setup_shop(client, coins_amount=300)
    buy(client, model_id=1, days=7)   # 65 Coins
    w = make_worker()
    run_jobs(w)
    token = csrf_of(client, "/server/1/miete")
    client.post("/server/1/verlaengern", data={"days": 2, "request_id": "x1", "csrf": token})
    assert coins.balance(c, 1) == 300 - 65 - 19
    # Warnung 3 Tage vorher
    set_until(1, timedelta(days=2))
    assert "läuft in" in client.get("/").text
    # Auto-Verlängern mit genug Coins
    client.post("/server/1/auto-verlaengern", data={"enabled": "1", "csrf": token})
    set_until(1, timedelta(seconds=-5))
    tasks.check_expiry(w)
    assert c.execute("SELECT state FROM servers").fetchone()[0] == "active"
    assert coins.balance(c, 1) == 300 - 65 - 19 - 65
    # zu wenig Coins → archivieren
    from hostly import db
    with db.transaction(c):
        coins.book(c, 1, -coins.balance(c, 1), "admin")
    (minecraft.data_dir(1) / "world").mkdir(parents=True, exist_ok=True)
    set_until(1, timedelta(seconds=-5))
    tasks.check_expiry(w)
    run_jobs(w)
    s = c.execute("SELECT * FROM servers").fetchone()
    assert s["state"] == "archived" and s["tunnel_id"] is None
    assert (minecraft.archive_dir(1) / "world").exists() and not minecraft.data_dir(1).exists()
    assert "hostly-mc-1" not in w.ops.containers
    assert "Auto-Verlängern fehlgeschlagen" in client.get("/").text

    # Reaktivieren
    with db.transaction(c):
        coins.book(c, 1, 100, "admin")
    client.post("/server/1/reaktivieren", data={"days": 1, "request_id": "x2", "csrf": token})
    run_jobs(w)
    s = c.execute("SELECT * FROM servers").fetchone()
    assert s["state"] == "active" and s["tunnel_id"] is not None
    assert (minecraft.data_dir(1) / "world").exists()


def test_delete_with_refund(client):
    c = setup_shop(client, coins_amount=1000)
    buy(client, model_id=1, days=10)  # 10 × 10 × 0,9 = 90
    w = make_worker()
    run_jobs(w)
    token = csrf_of(client, "/server/1/miete")
    r = client.post("/server/1/loeschen", data={"confirm_name": "falsch", "csrf": token})
    assert "genau eintippen" in r.text
    set_until(1, timedelta(days=9, hours=12))
    client.post("/server/1/loeschen", data={"confirm_name": "Survival", "csrf": token})
    run_jobs(w)
    # 9 volle Resttage (knapp unter 10) × 9 Coins/Tag = 81
    assert coins.balance(c, 1) == 1000 - 90 + 81
    assert c.execute("SELECT state, tunnel_id FROM servers").fetchone()[:] == ("deleted", None)
    assert not minecraft.data_dir(1).exists()


def test_admin_delete_without_refund(client):
    c = setup_shop(client, coins_amount=1000)
    buy(client, model_id=1, days=10)
    token = csrf_of(client, "/admin/server")
    client.post("/admin/server/1/loeschen", data={"refund": "nein", "csrf": token})
    assert coins.balance(c, 1) == 910


def test_join_history_and_version_pin(client):
    c = setup_shop(client)
    buy(client)
    w = make_worker()
    run_jobs(w)
    log = minecraft.data_dir(1) / "logs"
    log.mkdir(parents=True)
    (log / "latest.log").write_text(
        "[09:00:00] [Server thread/INFO]: Starting minecraft server version 1.21.4\n"
        "[09:01:00] [Server thread/INFO]: Steve joined the game\n"
        "[09:05:00] [Server thread/INFO]: Steve left the game\n")
    tasks.status_all(w)
    assert c.execute("SELECT mc_version FROM servers").fetchone()[0] == "1.21.4"
    row = c.execute("SELECT * FROM player_sessions").fetchone()
    assert row["minecraft_name"] == "Steve" and row["left_at"] is not None
    tasks.status_all(w)  # nicht doppelt zählen
    assert c.execute("SELECT COUNT(*) FROM player_sessions").fetchone()[0] == 1
    assert "Steve" in client.get("/server/1/spieler").text


def test_whitelist_op_motd_icon(client):
    c = setup_shop(client)
    buy(client)
    w = make_worker()
    run_jobs(w)
    token = csrf_of(client, "/server/1/spieler")
    client.post("/server/1/whitelist", data={"action": "on", "csrf": token})
    client.post("/server/1/whitelist", data={"action": "add", "name": "Alex", "csrf": token})
    assert client.post("/server/1/whitelist", data={"action": "add", "name": "x!", "csrf": token}).status_code == 400
    token = csrf_of(client, "/einstellungen")
    client.post("/einstellungen/minecraft", data={"minecraft_name": "Steve", "csrf": token})
    run_jobs(w)
    assert {"whitelist on", "whitelist add Alex", "op Steve"} <= set(w.rcon.commands)

    client.post("/server/1/motd", data={"text": "§aHallo\n§lWelt", "csrf": token})
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), "red").save(buf, "PNG")
    r = client.post("/server/1/icon", data={"csrf": token}, files={"icon": ("x.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200
    assert Image.open(minecraft.icon_file(1)).size == (64, 64)
    assert "Änderungen ausstehend" in client.get("/server/1").text
    client.post("/server/1/aktion", data={"action": "restart", "csrf": token})
    run_jobs(w)
    env = w.ops.containers["hostly-mc-1"]["spec"]["env"]
    assert env["MOTD"] == "§aHallo\n§lWelt" and env["OPS"] == "Steve"
    assert env["WHITELIST"] == "Alex" and env["ENABLE_WHITELIST"] == "TRUE"
    assert (minecraft.data_dir(1) / "server-icon.png").exists()
    assert c.execute("SELECT needs_restart FROM servers").fetchone()[0] == 0
    assert client.post("/server/1/icon", data={"csrf": token},
                       files={"icon": ("x.png", b"kein bild", "image/png")}).status_code == 400


def test_download_zip(client):
    setup_shop(client)
    buy(client)
    w = make_worker()
    run_jobs(w)
    world = minecraft.data_dir(1) / "world"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"x" * 100)
    (minecraft.data_dir(1) / "server.properties").write_text("level-name=world\n")
    token = csrf_of(client, "/server/1")
    client.post("/server/1/download", data={"part": "world", "csrf": token})
    run_jobs(w)
    assert "save-off" in w.rcon.commands and "save-on" in w.rcon.commands
    page = client.get("/server/1").text
    import re
    job_id = re.search(r'href="/download/(\d+)"', page).group(1)
    r = client.get(f"/download/{job_id}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    import io
    import zipfile
    assert zipfile.ZipFile(io.BytesIO(r.content)).namelist() == ["world/level.dat"]
    logout(client)
    register(client, "bob")
    assert client.get(f"/download/{job_id}").status_code == 404


def test_avatar(client):
    register(client)
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (50, 80), "blue").save(buf, "JPEG")
    token = csrf_of(client, "/einstellungen")
    client.post("/einstellungen/profilbild", data={"mode": "own", "csrf": token},
                files={"image": ("a.jpg", buf.getvalue(), "image/jpeg")})
    r = client.get("/profilbild/1.png")
    assert r.status_code == 200 and Image.open(io.BytesIO(r.content)).size == (128, 128)
    assert "/profilbild/1.png" in client.get("/").text
    r = client.post("/einstellungen/profilbild", data={"mode": "minecraft", "csrf": token})
    assert "zuerst deinen Minecraft-Namen" in r.text


