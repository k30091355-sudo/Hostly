"""Version 1.5.8: Minecraft-Server laufen stabiler (Speicher, .paused, OP/Whitelist offline, Gamerules, Welten)."""
import io
import json
import os
import time
import zipfile

from hostly import extensions, gamesettings, minecraft, modrinth
from hostly.db import add_job
from hostly.worker import tasks
from hostly.worker.jobs import Worker

from .conftest import conn
from .helpers import FakeOps, FakeRcon, buy, run_jobs, setup_shop


def _server(client):
    setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    return w


def test_java_heap_leaves_room_below_container_limit(client):
    w = _server(client)
    spec = w.ops.containers["hostly-mc-1"]["spec"]
    heap_mb = int(spec["env"]["MEMORY"].rstrip("M"))
    assert heap_mb == 3072 - 256                                  # Eisen: 3 GB − 256 MB
    assert spec["mem_limit"] // 2 ** 20 - heap_mb >= 700          # ≥ 0,7 GB für Java selbst


def test_stale_paused_file_from_before_reboot_is_removed(client):
    w = _server(client)
    flag = minecraft.data_dir(1) / ".paused"
    flag.write_text("")
    old = time.time() - 3600
    os.utime(flag, (old, old))
    w.clear_stale_pause(1, {"running": True, "started_at": time.time() - 60})
    assert not flag.exists()
    # echte Pause (nach dem Containerstart angelegt) bleibt
    flag.write_text("")
    w.clear_stale_pause(1, {"running": True, "started_at": time.time() - 600})
    assert flag.exists()
    w.clear_stale_pause(1, {"running": True, "started_at": None})
    assert flag.exists()


def test_new_container_starts_awake(client):
    w = _server(client)
    (minecraft.data_dir(1) / ".paused").write_text("")
    w.ops.containers["hostly-mc-1"]["running"] = False
    add_job(conn(), "start", 1)
    run_jobs(w)
    assert not (minecraft.data_dir(1) / ".paused").exists()


def test_deop_and_whitelist_remove_while_offline_edit_files(client):
    w = _server(client)
    data = minecraft.data_dir(1)
    (data / "ops.json").write_text(json.dumps([{"uuid": "a", "name": "AlterBesitzer", "level": 4},
                                               {"uuid": "b", "name": "Neu", "level": 4}]))
    (data / "whitelist.json").write_text(json.dumps([{"uuid": "c", "name": "Steve"}, {"uuid": "d", "name": "Alex"}]))
    w.ops.containers["hostly-mc-1"]["running"] = False
    add_job(conn(), "rcon", 1, payload={"commands": ["deop alterbesitzer", "op Neu", "whitelist remove Steve"]})
    run_jobs(w)
    assert [e["name"] for e in json.loads((data / "ops.json").read_text())] == ["Neu"]
    assert [e["name"] for e in json.loads((data / "whitelist.json").read_text())] == ["Alex"]


def test_empty_whitelist_is_cleared_on_start(client):
    w = _server(client)
    c = conn()
    c.execute("UPDATE servers SET whitelist_enabled = 1")
    (minecraft.data_dir(1) / "whitelist.json").write_text(json.dumps([{"uuid": "c", "name": "Steve"}]))
    add_job(c, "restart", 1)
    run_jobs(w)
    assert json.loads((minecraft.data_dir(1) / "whitelist.json").read_text()) == []


def test_gamerules_only_names_that_exist_in_that_version():
    rules = '{"locator_bar": false, "keep_inventory": true, "players_sleeping_percentage": 50, "pvp": false}'
    old = gamesettings.commands_for({"mc_version": "1.20.1", "gamerules": rules})
    assert old == ["gamerule keepInventory true", "gamerule playersSleepingPercentage 50"]
    assert "gamerule pvp false" in gamesettings.commands_for({"mc_version": "1.21.9", "gamerules": rules})
    assert gamesettings.commands_for({"mc_version": "1.16.5", "gamerules": rules}) == ["gamerule keepInventory true"]
    assert "gamerule locator_bar false" in gamesettings.commands_for({"mc_version": "26.1", "gamerules": rules})
    assert gamesettings.version_tuple("26.1") > gamesettings.version_tuple("1.21.11") > gamesettings.version_tuple("1.9")


def test_level_type_for_old_versions():
    assert minecraft.level_type("minecraft:flat", "1.21.4") == "minecraft:flat"
    assert minecraft.level_type("minecraft:large_biomes", "1.18.2") == "largeBiomes"
    assert minecraft.level_type("minecraft:normal", "1.16.5") == "default"
    assert minecraft.level_type("minecraft:amplified", "LATEST") == "minecraft:amplified"


def test_version_change_installs_new_required_dependency(client, monkeypatch):
    setup_shop(client)
    buy(client)
    c = conn()
    c.execute("""INSERT INTO server_extensions (server_id, source, kind, project_id, slug, title, version_id, filename,
                 url, enabled) VALUES (1, 'modrinth', 'plugin', 'P1', 'p1', 'P1', 'v1', 'p1.jar',
                 'https://cdn.modrinth.com/p1.jar', 1)""")
    new_v = {"id": "v2", "version_number": "2", "game_versions": ["1.21.4"],
             "files": [{"filename": "p1-2.jar", "url": "https://cdn.modrinth.com/p1-2.jar", "primary": True}],
             "dependencies": [{"project_id": "LIB", "dependency_type": "required"}]}
    lib_v = {"id": "l1", "version_number": "1", "game_versions": ["1.21.4"], "dependencies": [],
             "files": [{"filename": "lib.jar", "url": "https://cdn.modrinth.com/lib.jar", "primary": True}]}
    monkeypatch.setattr(modrinth, "best_version", lambda pid, loaders, v: new_v if pid == "P1" else lib_v)
    monkeypatch.setattr(modrinth, "project", lambda pid: {"id": pid, "slug": pid.lower(), "title": pid})
    server = c.execute("SELECT * FROM servers WHERE id = 1").fetchone()
    plan = extensions.plan_change(c, server, "PAPER", "1.21.4")
    extensions.apply_change(c, server, plan)
    rows = {r["project_id"]: r for r in c.execute("SELECT * FROM server_extensions")}
    assert rows["P1"]["filename"] == "p1-2.jar"
    assert rows["LIB"]["filename"] == "lib.jar" and rows["LIB"]["is_dependency"] == 1 and rows["LIB"]["enabled"] == 1


def _world_zip(marker: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("meinewelt/level.dat", marker)
        z.writestr("meinewelt/region/r.0.0.mca", "x")
    return buf.getvalue()


def test_uploading_active_world_stops_server_first(client):
    w = _server(client)
    from hostly import config
    (minecraft.data_dir(1) / "world").mkdir(exist_ok=True)
    (minecraft.data_dir(1) / "world" / "level.dat").write_text("alt")
    up = config.UPLOADS_DIR / "worlds"
    up.mkdir(parents=True, exist_ok=True)
    (up / "a.zip").write_bytes(_world_zip("neu"))
    w.ops.calls.clear()
    add_job(conn(), "world_upload", 1, payload={"file": "a.zip", "name": "world"})
    run_jobs(w)
    assert (minecraft.data_dir(1) / "world" / "level.dat").read_text() == "neu"
    assert w.ops.calls[0] == ("stop", "hostly-mc-1")               # erst stoppen …
    assert ("recreate", "hostly-mc-1") in w.ops.calls              # … dann wieder starten
    assert conn().execute("SELECT COUNT(*) FROM backups WHERE kind = 'vor-aenderung'").fetchone()[0] == 1
    # andere Welt hochladen: Server läuft einfach weiter
    (up / "b.zip").write_bytes(_world_zip("zweite"))
    w.ops.calls.clear()
    add_job(conn(), "world_upload", 1, payload={"file": "b.zip", "name": "zweite"})
    run_jobs(w)
    assert ("stop", "hostly-mc-1") not in w.ops.calls
    assert (minecraft.data_dir(1) / "zweite" / "level.dat").read_text() == "zweite"


def test_status_ignores_stale_pause_flag(client):
    w = _server(client)
    flag = minecraft.data_dir(1) / ".paused"
    flag.write_text("")
    os.utime(flag, (time.time() - 3600, time.time() - 3600))
    orig = w.ops.state
    w.ops.state = lambda name: {**orig(name), "started_at": time.time() - 30}
    tasks.update_status(w, conn(), 1)
    st = conn().execute("SELECT paused, players_online FROM server_status").fetchone()
    assert st["paused"] == 0 and st["players_online"] == 1


def test_stop_while_starting_waits_until_ready(client):
    """„stop“ in den ersten Sekunden nach dem Start ginge verloren → erst warten, bis der Server antwortet."""
    w = _server(client)
    orig = w.ops.state
    w.ops.state = lambda name: {**orig(name), "health": "starting"} if orig(name)["running"] else orig(name)
    w.rcon.commands.clear()
    w.graceful_stop(conn(), conn().execute("SELECT * FROM servers WHERE id = 1").fetchone())
    assert w.rcon.commands == ["list"] and ("stop", "hostly-mc-1") in w.ops.calls


def test_interrupted_create_is_finished_after_worker_restart(client):
    setup_shop(client)
    buy(client)
    c = conn()
    c.execute("UPDATE servers SET state = 'active'")       # Worker starb nach „aktiv setzen“, vor dem Container
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    assert "hostly-mc-1" in w.ops.containers


def test_rcon_status_lines_hidden_in_console():
    from hostly.web.routes.myservers import RCON_NOISE
    assert RCON_NOISE.search("[00:03:06] [RCON Listener #1/INFO]: Thread RCON Client /127.0.0.1 started")
    assert not RCON_NOISE.search("[00:03:06] [Server thread/INFO]: Steve joined the game")


def test_no_backup_when_disk_almost_full(client, monkeypatch):
    import shutil as sh
    import pytest
    w = _server(client)
    from collections import namedtuple
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(sh, "disk_usage", lambda p: Usage(100 * 1024 ** 3, 99 * 1024 ** 3, 1 * 1024 ** 3))
    with pytest.raises(RuntimeError, match="fast voll"):
        w.backup(conn(), conn().execute("SELECT * FROM servers WHERE id = 1").fetchone(), "taeglich")
    assert conn().execute("SELECT COUNT(*) FROM backups").fetchone()[0] == 0


def test_hopper_tweak_is_undone_once(tmp_path, monkeypatch):
    from hostly.worker import files
    monkeypatch.setattr(minecraft, "data_dir", lambda sid: tmp_path)
    (tmp_path / "config").mkdir()
    cfg = tmp_path / "config" / "paper-world-defaults.yml"
    cfg.write_text("hopper:\n  cooldown-when-full: true\n  disable-move-event: true\n")
    server = {"type": "PAPER", "id": 1}
    assert files.tune_paper(server, 2.0, dry_run=True)            # → „Neustart nötig“
    files.tune_paper(server, 2.0)
    assert "disable-move-event: false" in cfg.read_text()
    cfg.write_text(cfg.read_text().replace("disable-move-event: false", "disable-move-event: true"))
    files.tune_paper(server, 2.0)                                   # eigene Wahl des Besitzers bleibt
    assert "disable-move-event: true" in cfg.read_text()
