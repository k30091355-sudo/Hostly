"""Version 1.4.1: Fehlerbehebungen vor dem Release (SkyBlock/OneBlock, altes Icon, Paper-Join-Verlauf …)."""
from hostly import config, extensions, minecraft
from hostly.worker import files, tasks
from hostly.worker.jobs import Worker

from .conftest import conn, csrf_of
from .helpers import FakeOps, FakeRcon, buy, run_jobs, setup_shop


def test_new_server_ignores_leftovers_of_old_server_with_same_number(client):
    """Nach dem Zurücksetzen aller Accounts bekommt ein neuer Server wieder die Nummer 1 –
    er darf weder das alte Icon noch die alte Welt erben."""
    old_icon = minecraft.icon_file(1)
    old_icon.parent.mkdir(parents=True, exist_ok=True)
    old_icon.write_bytes(b"\x89PNG alt")
    old_world = minecraft.data_dir(1) / "world"
    old_world.mkdir(parents=True)
    (old_world / "level.dat").write_text("alt")
    (minecraft.data_dir(1) / "server-icon.png").write_bytes(b"alt")
    c = setup_shop(client)
    buy(client)
    page = client.get("/server/1/icon.png")
    assert page.headers["content-type"].startswith("image/svg")        # Standard-Logo, nicht das alte PNG
    run_jobs(Worker(FakeOps(), FakeRcon()))
    assert not (minecraft.data_dir(1) / "world" / "level.dat").exists()
    assert not (minecraft.data_dir(1) / "server-icon.png").exists()
    assert not old_icon.exists()
    moved = list((config.DATA_DIR / "verwaist").iterdir())
    assert len(moved) == 1 and (moved[0] / "daten" / "world" / "level.dat").exists()
    assert c.execute("SELECT state FROM servers").fetchone()[0] == "active"


def test_uploaded_icon_is_shown_and_copied(client):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    token = csrf_of(client, "/server/1/darstellung")
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (100, 80), "red").save(buf, "PNG")
    client.post("/server/1/icon", data={"csrf": token}, files={"icon": ("a.png", buf.getvalue(), "image/png")})
    assert client.get("/server/1/icon.png").headers["content-type"] == "image/png"
    client.post("/server/1/aktion", data={"action": "restart", "csrf": token})
    run_jobs(w)
    assert (minecraft.data_dir(1) / "server-icon.png").exists()


def test_paper_join_lines_are_recorded(client):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    log = minecraft.data_dir(1) / "logs"
    log.mkdir(parents=True)
    (log / "latest.log").write_text(
        "[09:01:00 INFO]: Steve joined the game\n"
        "[09:02:00 INFO]: <Bob> Alex joined the game\n"          # Chat-Trick zählt nicht
        "[09:05:00 INFO]: Steve left the game\n")
    tasks.status_all(w)
    rows = c.execute("SELECT * FROM player_sessions").fetchall()
    assert [r["minecraft_name"] for r in rows] == ["Steve"] and rows[0]["left_at"] is not None


def test_bentobox_addons_go_to_addons_folder():
    assert extensions.subfolder_for("plugin", {"dependencies": []}, "AOneBlock") == "BentoBox/addons"
    dep = {"dependencies": [{"project_id": extensions.BENTOBOX_ID, "dependency_type": "required"}]}
    assert extensions.subfolder_for("plugin", dep, "irgendwas") == "BentoBox/addons"
    assert extensions.subfolder_for("plugin", {"dependencies": []}, "worldedit") is None
    assert extensions.subfolder_for("mod", dep, "bskyblock") is None
    server = {"id": 1, "level_name": None}
    row = {"kind": "plugin", "filename": "BSkyBlock.jar", "subfolder": "BentoBox/addons"}
    active, _ = files.ext_paths(server, row)
    assert active == minecraft.data_dir(1) / "plugins" / "BentoBox" / "addons" / "BSkyBlock.jar"
    evil = {"kind": "plugin", "filename": "x.jar", "subfolder": "../../etc"}
    assert files.ext_paths(server, evil)[0] == minecraft.data_dir(1) / "plugins" / "etc" / "x.jar"


def test_addon_jar_in_plugins_is_moved(client, tmp_path):
    """Sicherheitsnetz: liegt ein Addon (addon.yml) direkt in plugins/, wird es verschoben."""
    import zipfile
    c = setup_shop(client)
    buy(client)
    run_jobs(Worker(FakeOps(), FakeRcon()))
    plugins = minecraft.data_dir(1) / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(plugins / "Addon.jar", "w") as z:
        z.writestr("addon.yml", "name: X")
        z.writestr("plugin.yml", "name: X")
    c.execute("""INSERT INTO server_extensions (server_id, source, kind, project_id, slug, title, filename)
                 VALUES (1, 'modrinth', 'plugin', 'p1', 'neues-addon', 'X', 'Addon.jar')""")
    server = c.execute("SELECT * FROM servers WHERE id = 1").fetchone()
    files.sync_extensions(c, server)
    assert (plugins / "BentoBox" / "addons" / "Addon.jar").exists() and not (plugins / "Addon.jar").exists()
    assert c.execute("SELECT subfolder FROM server_extensions").fetchone()[0] == "BentoBox/addons"


def test_active_world_cannot_be_deleted_without_level_name(client):
    c = setup_shop(client)
    buy(client)
    run_jobs(Worker(FakeOps(), FakeRcon()))
    token = csrf_of(client, "/server/1/welten")
    r = client.post("/server/1/welten", data={"action": "delete", "name": "world", "csrf": token})
    assert r.status_code == 400
    assert conn().execute("SELECT COUNT(*) FROM jobs WHERE kind = 'world_delete'").fetchone()[0] == 0


def test_empty_console_command_is_not_sent(client):
    c = setup_shop(client)
    buy(client)
    run_jobs(Worker(FakeOps(), FakeRcon()))
    token = csrf_of(client, "/server/1/konsole")
    client.post("/server/1/konsole", data={"command": "   ", "csrf": token})
    assert c.execute("SELECT COUNT(*) FROM jobs WHERE kind = 'command'").fetchone()[0] == 0


def test_new_world_also_resets_skyblock_islands(client):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    data = minecraft.data_dir(1)
    for d in ("world", "bskyblock_world", "bskyblock_world_nether", "plugins/BentoBox/database", "plugins/BentoBox/addons",
              "andere_welt"):
        (data / d).mkdir(parents=True, exist_ok=True)
        (data / d / "x").write_text("x")
    token = csrf_of(client, "/server/1/einstellungen")
    client.post("/server/1/neue-welt", data={"seed": "", "confirm": "1", "csrf": token})
    run_jobs(w)
    assert not (data / "bskyblock_world" / "x").exists() and not (data / "bskyblock_world_nether").exists()
    assert not (data / "plugins/BentoBox/database").exists()
    assert (data / "plugins/BentoBox/addons/x").exists() and (data / "andere_welt/x").exists()


def test_soon_templates_are_greyed_out_and_cannot_be_bought(client):
    c = setup_shop(client)
    page = client.get("/kaufen").text
    assert 'value="skyblock" disabled' in page and "Kommt bald" in page
    assert 'value="performance" disabled' not in page
    token = csrf_of(client, "/kaufen")
    r = client.post("/kaufen", data={"model_id": 2, "days": 1, "name": "X", "template": "oneblock", "csrf": token})
    assert r.status_code == 400 and c.execute("SELECT COUNT(*) FROM servers").fetchone()[0] == 0


# ---------- Version 1.5.0: Lag-/Absturz-Schutz ----------

def test_yaml_set_only_changes_defaults():
    text = "chunks:\n  max-auto-save-chunks-per-tick: 24\n  prevent-moving-into-unloaded-chunks: false\nmisc:\n  x: 1\n"
    out = files.yaml_set(text, ("chunks", "max-auto-save-chunks-per-tick"), "24", "8")
    assert "max-auto-save-chunks-per-tick: 8" in out and "misc:\n  x: 1" in out
    own = text.replace(": 24", ": 12")                                # selbst eingestellt → bleibt
    assert files.yaml_set(own, ("chunks", "max-auto-save-chunks-per-tick"), "24", "8") == own


def test_paper_tuning_and_restart_hint(client):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    cfg = minecraft.data_dir(1) / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "paper-global.yml").write_text("chunk-loading-basic:\n  player-max-chunk-generate-rate: -1.0\n"
                                          "chunk-system:\n  io-threads: -1\n  worker-threads: -1\n")
    (cfg / "paper-world-defaults.yml").write_text("collisions:\n  max-entity-collisions: 8\n")
    tasks.status_all(w)                                               # Paper hat Dateien angelegt → Neustart nötig
    assert c.execute("SELECT needs_restart FROM servers").fetchone()[0] == 1
    token = csrf_of(client, "/server/1")
    client.post("/server/1/aktion", data={"action": "restart", "csrf": token})
    run_jobs(w)
    g = (cfg / "paper-global.yml").read_text()
    assert "player-max-chunk-generate-rate: 40.0" in g and "worker-threads: 2" in g      # Eisen: 3 Kerne − 1
    assert "max-entity-collisions: 2" in (cfg / "paper-world-defaults.yml").read_text()
    env = w.ops.containers["hostly-mc-1"]["spec"]["env"]
    assert env["MAX_CHAINED_NEIGHBOR_UPDATES"] == "200000" and "MaxDirectMemorySize" in env["JVM_XX_OPTS"]
    assert c.execute("SELECT needs_restart FROM servers").fetchone()[0] == 0


def test_public_modpack_button(client):
    c = setup_shop(client)
    buy(client, server_type="FABRIC")
    run_jobs(Worker(FakeOps(), FakeRcon()))
    c.execute("UPDATE servers SET mc_version = '26.3', public_listed = 1")
    assert "Modpack herunterladen" not in client.get("/s/" + c.execute("SELECT short_code FROM servers").fetchone()[0]).text
    c.execute("""INSERT INTO server_extensions (server_id, source, kind, project_id, slug, title, filename, url, sha1, sha512,
                 size, client_side) VALUES (1, 'modrinth', 'mod', 'p', 'sodium', 'Sodium', 's.jar', 'https://cdn.modrinth.com/s.jar',
                 'a', 'b', 1, 'required')""")
    code = c.execute("SELECT short_code FROM servers").fetchone()[0]
    client.cookies.clear()                                            # auch ohne Login
    assert "Modpack herunterladen" in client.get(f"/s/{code}").text
    assert f"/modpack/{code}.mrpack" in client.get("/serverliste").text
    r = client.get(f"/modpack/{code}.mrpack")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-modrinth-modpack")
    import io, json, zipfile
    idx = json.loads(zipfile.ZipFile(io.BytesIO(r.content)).read("modrinth.index.json"))
    assert idx["files"][0]["env"]["client"] == "required" and r.headers["cache-control"] == "no-store"
    first = idx["versionId"]
    c.execute("""INSERT INTO server_extensions (server_id, source, kind, project_id, slug, title, filename, url, sha1,
                 sha512, size, client_side) VALUES (1, 'modrinth', 'mod', 'p2', 'appleskin', 'AppleSkin', 'a.jar',
                 'https://cdn.modrinth.com/a.jar', 'c', 'd', 1, 'optional')""")       # später hinzugefügt
    idx = json.loads(zipfile.ZipFile(io.BytesIO(client.get(f"/modpack/{code}.mrpack").content)).read("modrinth.index.json"))
    assert [f["path"] for f in idx["files"]] == ["mods/s.jar", "mods/a.jar"] and idx["versionId"] != first
    assert all(f["env"]["client"] == "required" for f in idx["files"])


def test_open_sessions_closed_on_restart_and_console_execute_block(client):
    from hostly import console
    assert console.is_blocked("execute as @a run minecraft:stop") and not console.is_blocked("say run stop")
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    log = minecraft.data_dir(1) / "logs"
    log.mkdir(parents=True)
    (log / "latest.log").write_text("[09:01:00 INFO]: Steve joined the game\n")   # danach Absturz, kein „left“
    tasks.status_all(w)
    with open(log / "latest.log", "a") as f:
        f.write("[09:30:00] [Server thread/INFO]: Starting minecraft server version 26.3\n")
    tasks.status_all(w)
    assert c.execute("SELECT left_at FROM player_sessions").fetchone()[0] is not None


def test_last_admin_cannot_delete_account(client):
    c = setup_shop(client)
    token = csrf_of(client, "/einstellungen")
    r = client.post("/einstellungen/account-loeschen", data={"password": "geheim123", "confirm": "1",
                                                             "csrf": token})
    assert r.status_code == 400 and c.execute("SELECT deleted_at FROM users WHERE id = 1").fetchone()[0] is None


def test_download_does_not_block_restart():
    import sqlite3
    from hostly.worker.jobs import claim_jobs
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, kind TEXT, server_id INTEGER, status TEXT, started_at TEXT)")
    c.executemany("INSERT INTO jobs (kind, server_id, status) VALUES (?, ?, ?)",
                  [("download", 1, "running"), ("restart", 1, "pending"), ("download", 2, "pending"),
                   ("start", 2, "pending")])
    got = [r["kind"] for r in claim_jobs(c, 5)]
    assert "restart" in got and "start" in got and "download" not in got   # ZIP läuft schon → kein zweites
