"""Stufe 7–8b: Backups, Erweiterungen (Modrinth simuliert), Versionen, Welten, Dateien, Absturz, Statistik."""
import io
import zipfile

import pytest

from hostly import db, extensions, minecraft, modrinth
from hostly.worker import files, tasks
from hostly.worker.jobs import Worker

from .conftest import conn, csrf_of, logout, register
from .helpers import FakeOps, FakeRcon, buy, run_jobs, setup_shop

PROJECTS = {
    "lithium": {"id": "P_LITH", "slug": "lithium", "title": "Lithium", "client_side": "optional"},
    "yungs": {"id": "P_YUNG", "slug": "yungs", "title": "YUNG's Dungeons", "client_side": "required"},
    "fabric-api": {"id": "P_FAPI", "slug": "fabric-api", "title": "Fabric API", "client_side": "required"},
    "serveronly": {"id": "P_SRV", "slug": "serveronly", "title": "Server Only", "client_side": "unsupported"},
}
BY_ID = {p["id"]: p for p in PROJECTS.values()}


def fake_version(pid, mc, deps=()):
    return {"id": f"V_{pid}_{mc}", "version_number": f"1.0+{mc}", "version_type": "release", "game_versions": [mc],
            "dependencies": [{"project_id": d, "dependency_type": "required"} for d in deps],
            "files": [{"primary": True, "filename": f"{pid}-{mc}.jar", "url": f"https://cdn.modrinth.com/{pid}.jar",
                       "hashes": {"sha1": "x", "sha512": "y"}, "size": 10}]}


@pytest.fixture
def fake_modrinth(monkeypatch):
    available = {"1.21.4": {"P_LITH", "P_YUNG", "P_FAPI", "P_SRV"}, "1.21.5": {"P_LITH", "P_FAPI"}}

    def project(ref):
        return PROJECTS.get(ref) or BY_ID.get(ref)

    def best_version(ref, loaders, mc):
        p = project(ref)
        if not p or p["id"] not in available.get(mc, set()):
            return None
        return fake_version(p["id"], mc, deps=["P_FAPI"] if p["id"] == "P_YUNG" else ())

    def version(vid):
        _, pid, mc = vid.split("_", 2)
        pid = "P_" + mc.split("_")[0] if False else vid[2:].rsplit("_", 1)[0]
        return fake_version(pid, vid.rsplit("_", 1)[1])

    monkeypatch.setattr(modrinth, "project", project)
    monkeypatch.setattr(modrinth, "best_version", best_version)
    monkeypatch.setattr(modrinth, "version", version)
    monkeypatch.setattr(modrinth, "versions", lambda ref, l, mc: [v for v in [best_version(ref, l, mc)] if v])
    monkeypatch.setattr(modrinth, "mojang_releases", lambda limit=30: ["1.21.5", "1.21.4"])
    monkeypatch.setattr(modrinth, "fabric_loader_version", lambda: "0.16.10")
    monkeypatch.setattr(modrinth, "search", lambda q, kind, t, mc, limit=20: [
        {"project_id": "P_LITH", "title": "Lithium", "description": "schnell", "downloads": 1000, "icon_url": None}])

    def fake_download(url, dest, sha1):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"jar")
    monkeypatch.setattr(files, "download", fake_download)


def fabric_server(client, c):
    buy(client, server_type="FABRIC")
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    c.execute("UPDATE servers SET mc_version = '1.21.4'")
    return w


def test_extensions_install_toggle_remove(client, fake_modrinth):
    c = setup_shop(client)
    w = fabric_server(client, c)
    assert "Lithium" in client.get("/server/1/erweiterungen/suche?q=lith&kind=mod").text
    token = csrf_of(client, "/server/1/erweiterungen")
    client.post("/server/1/erweiterungen", data={"project_id": "P_YUNG", "kind": "mod", "csrf": token})
    rows = c.execute("SELECT title, is_dependency FROM server_extensions ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [("YUNG's Dungeons", 0), ("Fabric API", 1)]   # Abhängigkeit automatisch
    run_jobs(w)
    mods = minecraft.data_dir(1) / "mods"
    assert sorted(p.name for p in mods.iterdir()) == ["P_FAPI-1.21.4.jar", "P_YUNG-1.21.4.jar"]
    client.post("/server/1/erweiterungen/1", data={"action": "toggle", "csrf": token})
    run_jobs(w)
    assert not (mods / "P_YUNG-1.21.4.jar").exists()
    assert (minecraft.data_dir(1) / "hostly-disabled" / "mods" / "P_YUNG-1.21.4.jar").exists()
    client.post("/server/1/erweiterungen/1", data={"action": "remove", "csrf": token})
    run_jobs(w)
    assert not (minecraft.data_dir(1) / "hostly-disabled" / "mods" / "P_YUNG-1.21.4.jar").exists()
    assert "Eigene Plugins" in client.get("/server/1/erweiterungen").text   # Support-Hinweis


def test_modpack_only_client_mods(client, fake_modrinth):
    c = setup_shop(client)
    fabric_server(client, c)
    token = csrf_of(client, "/server/1/erweiterungen")
    for pid in ("P_YUNG", "P_SRV"):
        client.post("/server/1/erweiterungen", data={"project_id": pid, "kind": "mod", "csrf": token})
    code = c.execute("SELECT short_code FROM servers").fetchone()[0]
    r = client.get(f"/modpack/{code}.mrpack")
    index = __import__("json").loads(zipfile.ZipFile(io.BytesIO(r.content)).read("modrinth.index.json"))
    paths = [f["path"] for f in index["files"]]
    assert "mods/P_YUNG-1.21.4.jar" in paths and "mods/P_SRV-1.21.4.jar" not in paths
    assert index["dependencies"]["minecraft"] == "1.21.4"


def test_admin_upload_and_user_cannot(client, fake_modrinth):
    c = setup_shop(client)
    w = fabric_server(client, c)
    token = csrf_of(client, "/server/1/erweiterungen")
    client.post("/server/1/erweiterungen-upload", data={"kind": "mod", "csrf": token},
                files={"file": ("eigen.jar", b"JAR", "application/java-archive")})
    run_jobs(w)
    assert (minecraft.data_dir(1) / "mods" / "eigen.jar").read_bytes() == b"JAR"
    # normaler User darf nicht hochladen
    c.execute("UPDATE users SET is_admin = 0")
    r = client.post("/server/1/erweiterungen-upload", data={"kind": "mod", "csrf": token},
                    files={"file": ("x.jar", b"X", "application/java-archive")})
    assert r.status_code == 404


def test_version_change_plan_backup_and_rebuild(client, fake_modrinth):
    c = setup_shop(client)
    w = fabric_server(client, c)
    token = csrf_of(client, "/server/1/erweiterungen")
    client.post("/server/1/erweiterungen", data={"project_id": "P_YUNG", "kind": "mod", "csrf": token})
    client.post("/server/1/erweiterungen", data={"project_id": "P_LITH", "kind": "mod", "csrf": token})
    run_jobs(w)
    page = client.get("/server/1/version?to_version=1.21.5&to_type=FABRIC").text
    assert "2 Erweiterungen werden automatisch aktualisiert" in page     # Lithium + Fabric API
    assert "1 Erweiterungen gibt es dafür nicht" in page                   # YUNG
    client.post("/server/1/version", data={"to_version": "1.21.5", "to_type": "FABRIC", "csrf": token})
    run_jobs(w)
    s = c.execute("SELECT mc_version FROM servers").fetchone()
    assert s[0] == "1.21.5"
    assert c.execute("SELECT kind, status FROM backups").fetchone()[:] == ("vor-aenderung", "fertig")
    assert w.ops.containers["hostly-mc-1"]["spec"]["env"]["VERSION"] == "1.21.5"
    mods = sorted(p.name for p in (minecraft.data_dir(1) / "mods").iterdir())
    assert mods == ["P_FAPI-1.21.5.jar", "P_LITH-1.21.5.jar"]


def test_template_purchase(client, fake_modrinth, monkeypatch):
    monkeypatch.setitem(extensions.TEMPLATES, "test", {"name": "T", "type": "FABRIC", "text": "",
                                                       "projects": [("yungs", "mod")]})
    c = setup_shop(client)
    token = csrf_of(client, "/kaufen")
    client.post("/kaufen", data={"model_id": 2, "days": 1, "name": "Tpl", "template": "test",
                                 "request_id": "t", "csrf": token})
    s = c.execute("SELECT * FROM servers").fetchone()
    assert s["type"] == "FABRIC" and s["mc_version"] == "1.21.4"   # 1.21.5 hat YUNG nicht
    assert c.execute("SELECT COUNT(*) FROM server_extensions").fetchone()[0] == 2


def test_backup_nightly_restore_and_cleanup(client, monkeypatch):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    level = minecraft.data_dir(1) / "world"
    level.mkdir(parents=True, exist_ok=True)
    (level / "level.dat").write_text("v1")
    (minecraft.data_dir(1) / ".paused").touch()      # eingefroren → nicht wecken
    w.rcon.commands.clear()
    import datetime as dt
    class Fake(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 22, 3, 0, tzinfo=tz)
    monkeypatch.setattr(tasks, "datetime", Fake)
    tasks.nightly_backups(w)
    assert w.rcon.commands == []
    b = c.execute("SELECT * FROM backups").fetchone()
    assert b["kind"] == "taeglich" and b["status"] == "fertig"
    (level / "level.dat").write_text("v2-kaputt")
    token = csrf_of(client, "/server/1/backups")
    client.post(f"/server/1/backups/{b['id']}/wiederherstellen", data={"csrf": token})
    run_jobs(w)
    assert (level / "level.dat").read_text() == "v1"
    kinds = [r[0] for r in c.execute("SELECT kind FROM backups ORDER BY id")]
    assert kinds == ["taeglich", "vor-wiederherstellung"]
    # Aufräumen: alt + neueres vorhanden → weg; angepinnt bleibt
    c.execute("UPDATE backups SET created_at = '2000-01-01 00:00:00' WHERE id = 1")
    tasks.cleanup_backups(w)
    assert [r[0] for r in c.execute("SELECT id FROM backups")] == [2]


def test_worlds_and_files(client):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    token = csrf_of(client, "/server/1/welten")
    client.post("/server/1/welten", data={"action": "new", "name": "flach", "level_type": "flat", "seed": "42", "csrf": token})
    run_jobs(w)
    env_server = c.execute("SELECT level_name, world_type, world_seed FROM servers").fetchone()
    assert tuple(env_server) == ("flach", "minecraft:flat", "42")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("MeineWelt/level.dat", "x")
        zf.writestr("MeineWelt/region/r.0.0.mca", "y")
    client.post("/server/1/welten", data={"action": "upload", "name": "hoch", "csrf": token},
                files={"file": ("w.zip", buf.getvalue(), "application/zip")})
    run_jobs(w)
    assert (minecraft.data_dir(1) / "hoch" / "region" / "r.0.0.mca").exists()
    assert "hoch" in client.get("/server/1/welten").text
    # Zip-Slip wird abgewehrt
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("level.dat", "x")
        zf.writestr("../../boese.txt", "y")
    client.post("/server/1/welten", data={"action": "upload", "name": "boese", "csrf": token},
                files={"file": ("b.zip", bad.getvalue(), "application/zip")})
    run_jobs(w)
    assert not (minecraft.data_dir(1).parent / "boese.txt").exists()

    # Dateimanager
    (minecraft.data_dir(1) / "server.properties").write_text("max-players=7\ndifficulty=easy\n")
    assert "server.properties" in client.get("/server/1/dateien").text
    r = client.post("/server/1/dateien", data={"action": "save", "path": "server.properties",
                                               "content": "max-players=99\ndifficulty=easy\n", "csrf": token})
    assert "max-players" in r.text and r.status_code == 400
    client.post("/server/1/dateien", data={"action": "save", "path": "server.properties",
                                           "content": "max-players=7\ndifficulty=hard\n", "csrf": token})
    run_jobs(w)
    assert "difficulty=hard" in (minecraft.data_dir(1) / "server.properties").read_text()
    assert client.post("/server/1/dateien", data={"action": "save", "path": "eula.txt", "content": "x",
                                                  "csrf": token}).status_code == 403
    assert client.get("/server/1/dateien?path=../../").status_code in (200, 303)
    assert client.post("/server/1/dateien", data={"action": "delete", "path": "../../db",
                                                  "csrf": token}).status_code == 400


def test_crash_protection(client):
    c = setup_shop(client)
    buy(client)
    w = Worker(FakeOps(), FakeRcon())
    run_jobs(w)
    original = w.ops.state
    count = {"n": 0}
    w.ops.state = lambda name: {**original(name), "restart_count": count["n"]}
    for i in range(1, 4):
        count["n"] = i
        tasks.status_all(w)
    s = c.execute("SELECT crash_locked FROM servers").fetchone()
    assert s[0] == 1 and c.execute("SELECT COUNT(*) FROM crashes").fetchone()[0] == 3
    assert "3× hintereinander abgestürzt" in client.get("/").text


def test_public_list_stats_and_code_datapack(client):
    c = setup_shop(client)
    token = csrf_of(client, "/kaufen")
    client.post("/kaufen", data={"model_id": 2, "server_type": "PAPER", "days": 1, "name": "Öffentlich",
                                 "public": "1", "request_id": "p", "csrf": token})
    w = Worker(FakeOps(), FakeRcon())
    db.set_setting(c, "public_url", "https://hostly.test.ts.net")
    run_jobs(w)
    tasks.status_all(w)
    logout(client)
    assert "Öffentlich" in client.get("/serverliste").text
    code = c.execute("SELECT short_code FROM servers").fetchone()[0]
    r = client.get(f"/s/{code}")
    assert r.status_code == 200 and "<svg" in r.text and "Spieler jetzt" in r.text
    assert client.get("/s/gibtsnicht").status_code == 404
    show = minecraft.data_dir(1) / "world" / "datapacks" / "hostly-code" / "data" / "hostly" / "function" / "show.mcfunction"
    assert code in show.read_text() and "hostly.test.ts.net/s/" in show.read_text()

