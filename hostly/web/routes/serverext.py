"""Server-Reiter aus Stufe 7–8b: Plugins/Mods, Version & Typ, Welten, Resourcepack, Dateien, Backups, Statistik."""
import hashlib
import json
import re
import secrets
import urllib.request

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from ... import config, db, extensions, filemanager, minecraft, modrinth
from ..deps import Ctx, Redirect, get_ctx
from .myservers import load, page

router = APIRouter()

MAX_WORLD_UPLOAD = 1024 * 1024 * 1024        # 1 GB
MAX_PACK_UPLOAD = 100 * 1024 * 1024          # 100 MB (Funnel-Bandbreite)
MAX_ADMIN_UPLOAD = 200 * 1024 * 1024
WORLD_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,32}$")


def require_active(server):
    if server["state"] != "active":
        raise HTTPException(404)


async def save_upload(upload: UploadFile, dest, limit: int) -> int:
    """Upload in Stücken speichern, mit Größengrenze."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(dest, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                dest.unlink(missing_ok=True)
                raise ValueError("Die Datei ist zu groß.")
            f.write(chunk)
    return size


# ---------- Plugins / Mods / Datapacks ----------

def _ext_page(ctx: Ctx, server, status_code: int = 200, **values):
    rows = ctx.conn.execute(
        "SELECT * FROM server_extensions WHERE server_id = ? ORDER BY is_dependency, title", (server["id"],)).fetchall()
    kinds = modrinth.kinds_for(server["type"])
    return page(ctx, "servers/extensions.html", server, status_code, rows=rows, kinds=kinds, **values)


@router.get("/server/{server_id}/erweiterungen", response_class=HTMLResponse)
def ext_page(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    return _ext_page(ctx, server)


@router.get("/server/{server_id}/erweiterungen/suche", response_class=HTMLResponse)
def ext_search(server_id: int, q: str = "", kind: str = "", ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    if server["mc_version"] == "LATEST":
        return HTMLResponse(f'<p class="alert warn small">{ctx.t("Starte den Server einmal, damit Hostly die Minecraft-Version kennt.")}</p>')
    kind = kind if kind in modrinth.kinds_for(server["type"]) else modrinth.kinds_for(server["type"])[0]
    try:
        hits = modrinth.search(q, kind, server["type"], server["mc_version"])
    except modrinth.ModrinthError as exc:
        return HTMLResponse(f'<p class="alert error small">{ctx.t(str(exc))}</p>')
    installed = {r[0] for r in ctx.conn.execute("SELECT project_id FROM server_extensions WHERE server_id = ?", (server_id,))}
    return ctx.render("servers/_ext_results.html", server=server, hits=hits, kind=kind, installed=installed)


@router.post("/server/{server_id}/erweiterungen")
def ext_install(server_id: int, project_id: str = Form(...), kind: str = Form(...), csrf: str = Form(""),
                ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    ctx.check_csrf(csrf)
    if kind not in modrinth.kinds_for(server["type"]) or server["mc_version"] == "LATEST":
        raise Redirect(f"/server/{server_id}/erweiterungen")
    try:
        entries = extensions.resolve(server["type"], server["mc_version"], project_id, kind)
    except (extensions.ExtensionError, modrinth.ModrinthError) as exc:
        return _ext_page(ctx, server, 400, error=ctx.t(getattr(exc, "message", None) or str(exc)))
    with db.transaction(ctx.conn):
        extensions.add_entries(ctx.conn, server_id, entries)
        extensions.mark_changed(ctx.conn, server_id, ctx.user["id"])
    raise Redirect(f"/server/{server_id}/erweiterungen")


@router.post("/server/{server_id}/erweiterungen/{ext_id}")
def ext_change(server_id: int, ext_id: int, action: str = Form(...), version_id: str = Form(""), csrf: str = Form(""),
               ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    ctx.check_csrf(csrf)
    row = ctx.conn.execute("SELECT * FROM server_extensions WHERE id = ? AND server_id = ?", (ext_id, server_id)).fetchone()
    if row is None:
        raise HTTPException(404)
    with db.transaction(ctx.conn):
        if action == "toggle":
            ctx.conn.execute("UPDATE server_extensions SET enabled = 1 - enabled WHERE id = ?", (ext_id,))
        elif action == "remove":
            ctx.conn.execute("DELETE FROM server_extensions WHERE id = ?", (ext_id,))
        elif action == "version" and version_id and row["source"] == "modrinth":
            try:
                entries = extensions.resolve(server["type"], server["mc_version"], row["project_id"], row["kind"],
                                             version_id=version_id)
            except (extensions.ExtensionError, modrinth.ModrinthError) as exc:
                return _ext_page(ctx, server, 400, error=ctx.t(getattr(exc, "message", None) or str(exc)))
            extensions.add_entries(ctx.conn, server_id, entries)
        extensions.mark_changed(ctx.conn, server_id, ctx.user["id"])
    raise Redirect(f"/server/{server_id}/erweiterungen")


@router.get("/server/{server_id}/erweiterungen/{ext_id}/versionen", response_class=HTMLResponse)
def ext_versions(server_id: int, ext_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    row = ctx.conn.execute("SELECT * FROM server_extensions WHERE id = ? AND server_id = ?", (ext_id, server_id)).fetchone()
    if row is None or row["source"] != "modrinth":
        raise HTTPException(404)
    try:
        vs = modrinth.versions(row["project_id"], modrinth.loaders_for(row["kind"], server["type"]), server["mc_version"])
    except modrinth.ModrinthError as exc:
        return HTMLResponse(f'<p class="alert error small">{ctx.t(str(exc))}</p>')
    return ctx.render("servers/_ext_versions.html", server=server, row=row, versions=vs[:20])


@router.post("/server/{server_id}/erweiterungen-upload")
async def ext_admin_upload(server_id: int, kind: str = Form(...), file: UploadFile = File(...), csrf: str = Form(""),
                           ctx: Ctx = Depends(get_ctx)):
    """Nur Admin: eigene Plugin-/Mod-/Datapack-Datei hochladen (Support-Fälle)."""
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    if not ctx.is_admin or kind not in extensions.FOLDERS:
        raise HTTPException(404)
    name = re.sub(r"[^A-Za-z0-9._+\-]", "_", (file.filename or "datei.jar"))[:120]
    dest = config.UPLOADS_DIR / "admin-files" / str(server_id) / name
    try:
        size = await save_upload(file, dest, MAX_ADMIN_UPLOAD)
    except ValueError as exc:
        return _ext_page(ctx, server, 400, error=ctx.t(str(exc)))
    with db.transaction(ctx.conn):
        ctx.conn.execute(
            """INSERT INTO server_extensions (server_id, source, kind, title, filename, size, project_id)
               VALUES (?, 'upload', ?, ?, ?, ?, ?)""",
            (server_id, kind, name, name, size, "upload:" + name))
        extensions.mark_changed(ctx.conn, server_id, ctx.user["id"])
    raise Redirect(f"/server/{server_id}/erweiterungen")


# ---------- Modpack für Spieler (.mrpack, nur Fabric) ----------

@router.get("/modpack/{short_code}.mrpack")
def modpack(short_code: str, ctx: Ctx = Depends(get_ctx)):
    import io
    import zipfile
    from fastapi.responses import Response

    server = ctx.conn.execute("SELECT * FROM servers WHERE short_code = ? AND state = 'active' AND type = 'FABRIC'",
                              (short_code,)).fetchone()
    if server is None or server["mc_version"] == "LATEST":
        raise HTTPException(404)
    rows = ctx.conn.execute(
        """SELECT * FROM server_extensions WHERE server_id = ? AND enabled = 1 AND source = 'modrinth' AND kind = 'mod'
           AND COALESCE(client_side, 'optional') != 'unsupported'""", (server["id"],)).fetchall()
    index = {
        "formatVersion": 1, "game": "minecraft", "versionId": server["short_code"],
        "name": f"{server['name']} (Hostly)",
        "files": [{"path": f"mods/{r['filename']}", "hashes": {"sha1": r["sha1"], "sha512": r["sha512"]},
                   "env": {"client": "required" if r["client_side"] == "required" else "optional", "server": "required"},
                   "downloads": [r["url"]], "fileSize": r["size"]} for r in rows],
        "dependencies": {"minecraft": server["mc_version"], "fabric-loader": modrinth.fabric_loader_version()},
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modrinth.index.json", json.dumps(index, indent=2))
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", server["name"])[:40] or "modpack"
    return Response(buf.getvalue(), media_type="application/x-modrinth-modpack+zip",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.mrpack"'})


# ---------- Version & Typ ----------

@router.get("/server/{server_id}/version", response_class=HTMLResponse)
def version_page(server_id: int, to_version: str = "", to_type: str = "", ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    error, plan, versions_list = None, None, []
    try:
        versions_list = modrinth.mojang_releases(30)
    except modrinth.ModrinthError as exc:
        error = ctx.t(str(exc))
    if to_version or to_type:
        to_version = to_version or server["mc_version"]
        to_type = to_type if to_type in config.SERVER_TYPES else server["type"]
        if to_version not in versions_list:
            error = ctx.t("Unbekannte Version.")
        else:
            try:
                plan = extensions.plan_change(ctx.conn, server, to_type, to_version)
            except modrinth.ModrinthError as exc:
                error = ctx.t(str(exc))
    return page(ctx, "servers/version.html", server, versions_list=versions_list, plan=plan, error=error,
                to_version=to_version, to_type=to_type, types=config.SERVER_TYPES)


@router.post("/server/{server_id}/version")
def version_apply(server_id: int, to_version: str = Form(...), to_type: str = Form(...), csrf: str = Form(""),
                  ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    ctx.check_csrf(csrf)
    if to_type not in config.SERVER_TYPES or to_version not in modrinth.mojang_releases(30):
        raise Redirect(f"/server/{server_id}/version")
    plan = extensions.plan_change(ctx.conn, server, to_type, to_version)
    with db.transaction(ctx.conn):
        extensions.apply_change(ctx.conn, server, plan)
        ctx.conn.execute("UPDATE servers SET mc_version = ?, type = ? WHERE id = ?", (to_version, to_type, server_id))
        db.add_job(ctx.conn, "rebuild", server_id, ctx.user["id"])   # Backup → Dateien → Neustart
        db.audit(ctx.conn, ctx.user["id"], "server_version", f"#{server_id} {server['type']} {server['mc_version']} → {to_type} {to_version}")
    raise Redirect(f"/server/{server_id}")


# ---------- Welten + Resourcepack ----------

def list_worlds(server_id: int) -> list[str]:
    data = minecraft.data_dir(server_id)
    if not data.exists():
        return []
    return sorted(p.name for p in data.iterdir() if p.is_dir() and (p / "level.dat").exists())


def _worlds_page(ctx: Ctx, server, status_code: int = 200, **values):
    return page(ctx, "servers/worlds.html", server, status_code, worlds=list_worlds(server["id"]), **values)


@router.get("/server/{server_id}/welten", response_class=HTMLResponse)
def worlds_page(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    return _worlds_page(ctx, server)


@router.post("/server/{server_id}/welten")
async def worlds_action(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    form = await ctx.request.form()
    ctx.check_csrf(form.get("csrf"))
    action, name = form.get("action"), (form.get("name") or "").strip()
    if action in ("activate", "new", "delete", "upload") and not WORLD_NAME_RE.match(name):
        return _worlds_page(ctx, server, 400, error=ctx.t("Weltname: 1–32 Zeichen, nur Buchstaben, Zahlen, - und _."))
    if action == "activate" and name in list_worlds(server_id):
        ctx.conn.execute("UPDATE servers SET level_name = ?, world_seed = NULL, world_type = NULL, needs_restart = 1 WHERE id = ?",
                         (name, server_id))
    elif action == "new":
        if name in list_worlds(server_id):
            return _worlds_page(ctx, server, 400, error=ctx.t("Diese Welt gibt es schon."))
        level_type = form.get("level_type") if form.get("level_type") in ("normal", "flat", "large_biomes", "amplified") else "normal"
        seed = (form.get("seed") or "").strip()[:40] or None
        ctx.conn.execute("UPDATE servers SET level_name = ?, world_seed = ?, world_type = ?, needs_restart = 1 WHERE id = ?",
                         (name, seed, "minecraft:" + level_type, server_id))
    elif action == "delete":
        if name == server["level_name"]:
            return _worlds_page(ctx, server, 400, error=ctx.t("Die aktive Welt kann nicht gelöscht werden."))
        db.add_job(ctx.conn, "world_delete", server_id, ctx.user["id"], {"name": name})
    elif action == "upload":
        upload = form.get("file")
        if not upload or not getattr(upload, "filename", ""):
            return _worlds_page(ctx, server, 400, error=ctx.t("Bitte eine ZIP-Datei auswählen."))
        fname = f"{server_id}-{secrets.token_hex(6)}.zip"
        try:
            await save_upload(upload, config.UPLOADS_DIR / "worlds" / fname, MAX_WORLD_UPLOAD)
        except ValueError:
            return _worlds_page(ctx, server, 400, error=ctx.t("Die Datei ist zu groß (höchstens 1 GB)."))
        db.add_job(ctx.conn, "world_upload", server_id, ctx.user["id"], {"file": fname, "name": name})
    elif action == "pack_remove":
        ctx.conn.execute("UPDATE servers SET resource_pack_url = NULL, resource_pack_sha1 = NULL, needs_restart = 1 WHERE id = ?",
                         (server_id,))
    elif action == "pack_enforce":
        ctx.conn.execute("UPDATE servers SET resource_pack_enforce = ?, needs_restart = 1 WHERE id = ?",
                         (1 if form.get("enforce") else 0, server_id))
    elif action == "pack_upload":
        upload = form.get("file")
        if not upload or not getattr(upload, "filename", "").lower().endswith(".zip"):
            return _worlds_page(ctx, server, 400, error=ctx.t("Bitte eine ZIP-Datei auswählen."))
        tmp = config.UPLOADS_DIR / "resourcepacks" / f"tmp-{secrets.token_hex(6)}.zip"
        try:
            await save_upload(upload, tmp, MAX_PACK_UPLOAD)
        except ValueError:
            return _worlds_page(ctx, server, 400, error=ctx.t("Die Datei ist zu groß (höchstens 100 MB)."))
        _store_pack(ctx, server_id, tmp)
    elif action == "pack_modrinth":
        try:
            _modrinth_pack(ctx, server, (form.get("project") or "").strip())
        except (ValueError, modrinth.ModrinthError) as exc:
            return _worlds_page(ctx, server, 400, error=ctx.t(str(exc)))
    raise Redirect(f"/server/{server_id}/welten")


def _public_base(ctx: Ctx) -> str:
    proto = ctx.request.headers.get("x-forwarded-proto", ctx.request.url.scheme)
    host = ctx.request.headers.get("host", "localhost:8000")
    if host.endswith(".ts.net"):
        proto = "https"
    return f"{proto}://{host}"


def _store_pack(ctx: Ctx, server_id: int, tmp) -> None:
    sha1 = hashlib.sha1(tmp.read_bytes()).hexdigest()
    final = config.UPLOADS_DIR / "resourcepacks" / f"{sha1}.zip"
    tmp.replace(final)
    ctx.conn.execute("UPDATE servers SET resource_pack_url = ?, resource_pack_sha1 = ?, needs_restart = 1 WHERE id = ?",
                     (f"{_public_base(ctx)}/rp/{final.name}", sha1, server_id))


def _modrinth_pack(ctx: Ctx, server, project: str) -> None:
    v = modrinth.best_version(project, ["minecraft"], server["mc_version"])
    if v is None:
        raise ValueError("Dieses Resourcepack gibt es nicht für deine Minecraft-Version.")
    f = modrinth.primary_file(v)
    if f.get("size", 0) > MAX_PACK_UPLOAD or not f["url"].startswith("https://cdn.modrinth.com/"):
        raise ValueError("Das Resourcepack ist zu groß (höchstens 100 MB).")
    tmp = config.UPLOADS_DIR / "resourcepacks" / f"tmp-{secrets.token_hex(6)}.zip"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(f["url"], headers={"User-Agent": modrinth.USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
        out.write(resp.read(MAX_PACK_UPLOAD + 1))
    _store_pack(ctx, server["id"], tmp)


@router.get("/server/{server_id}/welten/packsuche", response_class=HTMLResponse)
def pack_search(server_id: int, q: str = "", ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    if server["mc_version"] == "LATEST":
        return HTMLResponse(f'<p class="alert warn small">{ctx.t("Starte den Server einmal, damit Hostly die Minecraft-Version kennt.")}</p>')
    try:
        hits = modrinth.search(q, "resourcepack", server["type"], server["mc_version"], limit=10)
    except modrinth.ModrinthError as exc:
        return HTMLResponse(f'<p class="alert error small">{ctx.t(str(exc))}</p>')
    return ctx.render("servers/_pack_results.html", server=server, hits=hits)


@router.get("/rp/{filename}")
def resource_pack_file(filename: str):
    from fastapi.responses import FileResponse

    if not re.fullmatch(r"[0-9a-f]{40}\.zip", filename):
        raise HTTPException(404)
    path = config.UPLOADS_DIR / "resourcepacks" / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/zip")


# ---------- Dateimanager ----------

@router.get("/server/{server_id}/dateien", response_class=HTMLResponse)
def files_page(server_id: int, path: str = "", ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    target = filemanager.resolve(server_id, path)
    if target is None or not target.exists():
        raise Redirect(f"/server/{server_id}/dateien")
    rel = str(target.relative_to(minecraft.data_dir(server_id).resolve()))
    rel = "" if rel == "." else rel
    parent = "/".join(rel.split("/")[:-1])
    if target.is_dir():
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        items = [{"name": p.name, "dir": p.is_dir(), "size": p.stat().st_size if p.is_file() else 0,
                  "rel": f"{rel}/{p.name}".strip("/"), "locked": filemanager.is_locked(f"{rel}/{p.name}")}
                 for p in entries if not p.is_symlink()]
        return page(ctx, "servers/files.html", server, rel=rel, parent=parent, items=items, content=None)
    content, editable = None, False
    if filemanager.is_text(target) and target.stat().st_size <= filemanager.MAX_EDIT_BYTES:
        content = target.read_text(encoding="utf-8", errors="replace")
        editable = not filemanager.is_locked(rel)
    return page(ctx, "servers/files.html", server, rel=rel, parent=parent, items=None, content=content,
                editable=editable, saved=ctx.request.query_params.get("ok"))


@router.post("/server/{server_id}/dateien")
async def files_action(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    form = await ctx.request.form()
    ctx.check_csrf(form.get("csrf"))
    action, rel = form.get("action"), (form.get("path") or "").strip("/")
    target = filemanager.resolve(server_id, rel)
    if target is None or not rel:
        raise HTTPException(400)
    parent = "/".join(rel.split("/")[:-1])
    if action == "save":
        if filemanager.is_locked(rel) or not filemanager.is_text(target):
            raise HTTPException(403)
        content = (form.get("content") or "").replace("\r\n", "\n")
        if len(content.encode()) > filemanager.MAX_EDIT_BYTES:
            raise HTTPException(413)
        if target.name == "server.properties" and target.exists():
            changed = filemanager.protected_changes(target.read_text(errors="replace"), content)
            if changed:
                return page(ctx, "servers/files.html", server, 400, rel=rel, parent=parent, items=None,
                            content=content, editable=True,
                            error=ctx.t("Diese Einstellungen legt Hostly fest und können nicht geändert werden: {keys}",
                                        keys=", ".join(changed)))
        db.add_job(ctx.conn, "file_write", server_id, ctx.user["id"], {"path": rel, "content": content})
        ctx.conn.execute("UPDATE servers SET needs_restart = 1 WHERE id = ?", (server_id,))
        raise Redirect(f"/server/{server_id}/dateien?path={rel}&ok=1")
    if action == "delete":
        if filemanager.is_locked(rel):
            raise HTTPException(403)
        db.add_job(ctx.conn, "file_delete", server_id, ctx.user["id"], {"path": rel})
        raise Redirect(f"/server/{server_id}/dateien?path={parent}")
    if action == "upload" and ctx.is_admin:   # nur Admin (Support-Fälle)
        upload = form.get("file")
        if not upload or not getattr(upload, "filename", ""):
            raise Redirect(f"/server/{server_id}/dateien?path={rel}")
        name = re.sub(r"[^A-Za-z0-9._+\-]", "_", upload.filename)[:120]
        tmpname = f"{secrets.token_hex(6)}-{name}"
        await save_upload(upload, config.UPLOADS_DIR / "admin-files" / str(server_id) / "tmp" / tmpname, MAX_ADMIN_UPLOAD)
        db.add_job(ctx.conn, "file_put", server_id, ctx.user["id"], {"file": tmpname, "path": f"{rel}/{name}".strip("/")})
        raise Redirect(f"/server/{server_id}/dateien?path={rel}")
    raise HTTPException(400)


# ---------- Backups ----------

@router.get("/server/{server_id}/backups", response_class=HTMLResponse)
def backups_page(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    rows = ctx.conn.execute("SELECT * FROM backups WHERE server_id = ? ORDER BY id DESC", (server_id,)).fetchall()
    return page(ctx, "servers/backups.html", server, rows=rows)


@router.post("/server/{server_id}/backups/{backup_id}/wiederherstellen")
def restore(server_id: int, backup_id: int, csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    require_active(server)
    ctx.check_csrf(csrf)
    row = ctx.conn.execute("SELECT 1 FROM backups WHERE id = ? AND server_id = ? AND status = 'fertig'",
                           (backup_id, server_id)).fetchone()
    if row:
        db.add_job(ctx.conn, "restore", server_id, ctx.user["id"], {"backup_id": backup_id})
    raise Redirect(f"/server/{server_id}")


# ---------- Statistik-Reiter (Kürzel, öffentlich listen) ----------

@router.get("/server/{server_id}/statistik", response_class=HTMLResponse)
def stats_tab(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    return page(ctx, "servers/stats_tab.html", server)


@router.post("/server/{server_id}/oeffentlich")
def set_public(server_id: int, public: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    load(ctx, server_id)
    ctx.check_csrf(csrf)
    ctx.conn.execute("UPDATE servers SET public_listed = ? WHERE id = ?", (1 if public else 0, server_id))
    raise Redirect(f"/server/{server_id}/statistik")
