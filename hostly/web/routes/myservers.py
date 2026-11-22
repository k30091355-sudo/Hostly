"""„Meine Server“: Übersicht, Steuerung, Konsole, Darstellung, Spieler, Miete, Download."""
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from ... import config, console, db, images, minecraft, motd, servers
from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()

LOG_TAIL_BYTES = 64 * 1024
ACTIONS = ("start", "stop", "restart", "reload")


# ---------- Hilfen ----------

def load(ctx: Ctx, server_id: int):
    """Server laden – nur für Besitzer oder Admin."""
    ctx.require_login()
    server = ctx.conn.execute(
        """SELECT s.*, m.name AS model_name, m.ram_gb, m.max_players, m.price_per_day,
                  t.public_address
           FROM servers s JOIN models m ON m.id = s.model_id LEFT JOIN tunnels t ON t.id = s.tunnel_id
           WHERE s.id = ? AND s.state != 'deleted'""",
        (server_id,),
    ).fetchone()
    if server is None or not ctx.can_manage(server):
        raise HTTPException(404)
    return server


def status_of(ctx: Ctx, server_id: int):
    return ctx.conn.execute("SELECT * FROM server_status WHERE server_id = ?", (server_id,)).fetchone()


def busy_job(ctx: Ctx, server_id: int):
    return ctx.conn.execute(
        """SELECT * FROM jobs WHERE server_id = ? AND status IN ('pending', 'running')
           AND kind NOT IN ('command', 'rcon', 'download') ORDER BY id LIMIT 1""",
        (server_id,),
    ).fetchone()


def page(ctx: Ctx, template: str, server, status_code: int = 200, **values):
    st = status_of(ctx, server["id"])
    label, cls = servers.display_status(server, st)
    return ctx.render(template, status_code=status_code, server=server, st=st, status_label=label,
                      status_class=cls, busy=busy_job(ctx, server["id"]), **values)


def is_active(server) -> bool:
    return server["state"] == "active"


# ---------- Liste ----------

@router.get("/server", response_class=HTMLResponse)
def my_servers(ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    rows = ctx.conn.execute(
        """SELECT s.*, m.name AS model_name, t.public_address,
                  st.running, st.paused, st.health, st.players_online, st.players_max
           FROM servers s JOIN models m ON m.id = s.model_id LEFT JOIN tunnels t ON t.id = s.tunnel_id
           LEFT JOIN server_status st ON st.server_id = s.id
           WHERE s.owner_id = ? AND s.state != 'deleted' ORDER BY s.state = 'archived', s.id DESC""",
        (ctx.user["id"],),
    ).fetchall()
    items = [(r, *servers.display_status(r, r if r["running"] is not None else None)) for r in rows]
    return ctx.render("servers/list.html", items=items)


# ---------- Übersicht + Steuerung ----------

@router.get("/server/{server_id}", response_class=HTMLResponse)
def overview(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    downloads = ctx.conn.execute(
        "SELECT * FROM jobs WHERE server_id = ? AND kind = 'download' AND created_at > datetime('now', '-1 day') ORDER BY id DESC LIMIT 5",
        (server_id,),
    ).fetchall()
    return page(ctx, "servers/overview.html", server, new=ctx.request.query_params.get("neu") == "1",
                downloads=downloads)


@router.get("/server/{server_id}/status", response_class=HTMLResponse)
def status_fragment(server_id: int, ctx: Ctx = Depends(get_ctx)):
    """Nur aus der Datenbank – fragt den Minecraft-Server nie direkt an (weckt ihn nicht)."""
    server = load(ctx, server_id)
    return page(ctx, "servers/_status.html", server)


@router.post("/server/{server_id}/aktion")
def action(server_id: int, action: str = Form(...), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    if action in ACTIONS and is_active(server) and busy_job(ctx, server_id) is None:
        db.add_job(ctx.conn, action, server_id, ctx.user["id"])
    raise Redirect(f"/server/{server_id}")


# ---------- Konsole ----------

def read_log_tail(server_id: int, lines: int = 300) -> str:
    path = minecraft.data_dir(server_id) / "logs" / "latest.log"
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        size = path.stat().st_size
        f.seek(max(0, size - LOG_TAIL_BYTES))
        data = f.read().decode("utf-8", errors="replace")
    return "\n".join(data.splitlines()[-lines:])


def recent_commands(ctx: Ctx, server_id: int):
    return ctx.conn.execute(
        "SELECT * FROM jobs WHERE server_id = ? AND kind = 'command' ORDER BY id DESC LIMIT 10", (server_id,)
    ).fetchall()


@router.get("/server/{server_id}/konsole", response_class=HTMLResponse)
def console_page(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    return page(ctx, "servers/console.html", server, log=read_log_tail(server_id),
                commands=recent_commands(ctx, server_id))


@router.get("/server/{server_id}/konsole/log", response_class=HTMLResponse)
def console_log(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    return ctx.render("servers/_console_log.html", server=server, log=read_log_tail(server_id),
                      commands=recent_commands(ctx, server_id))


@router.post("/server/{server_id}/konsole")
def console_command(server_id: int, command: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    cmd = console.clean(command)
    error = None
    if not is_active(server):
        error = "Der Server ist nicht aktiv."
    elif console.is_blocked(cmd):
        error = "Dieser Befehl ist gesperrt – bitte die Knöpfe benutzen (Stoppen, Neustarten, Reload)."
    else:
        db.add_job(ctx.conn, "command", server_id, ctx.user["id"], {"command": cmd})
    if ctx.request.headers.get("hx-request"):
        if error:
            return HTMLResponse(f'<div class="alert error small">{ctx.t(error)}</div>')
        return HTMLResponse(f'<div class="hint good">{ctx.t("Befehl gesendet.")}</div>')
    if error:
        return page(ctx, "servers/console.html", server, 400, log=read_log_tail(server_id),
                    commands=recent_commands(ctx, server_id), error=ctx.t(error))
    raise Redirect(f"/server/{server_id}/konsole")


# ---------- Darstellung: Name, MOTD, Icon ----------

@router.get("/server/{server_id}/darstellung", response_class=HTMLResponse)
def appearance(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    return page(ctx, "servers/appearance.html", server, saved=ctx.request.query_params.get("ok"),
                has_icon=minecraft.icon_file(server_id).exists())


@router.post("/server/{server_id}/name")
def rename(server_id: int, name: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    name = name.strip()
    err = servers.check_name(name)
    if err:
        return page(ctx, "servers/appearance.html", server, 400, error=ctx.t(err),
                    has_icon=minecraft.icon_file(server_id).exists())
    ctx.conn.execute("UPDATE servers SET name = ? WHERE id = ?", (name, server_id))
    raise Redirect(f"/server/{server_id}/darstellung?ok=name")


@router.post("/server/{server_id}/motd")
def save_motd(server_id: int, text: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    text = text.replace("\r", "").strip("\n")
    err = motd.check(text)
    if err:
        return page(ctx, "servers/appearance.html", server, 400, error=ctx.t(err), motd_text=text,
                    has_icon=minecraft.icon_file(server_id).exists())
    ctx.conn.execute("UPDATE servers SET motd = ?, needs_restart = 1 WHERE id = ?", (text or None, server_id))
    raise Redirect(f"/server/{server_id}/darstellung?ok=motd")


@router.post("/server/{server_id}/icon")
async def upload_icon(server_id: int, icon: UploadFile = File(...), csrf: str = Form(""),
                      ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    data = await icon.read(images.MAX_UPLOAD_BYTES + 1)
    try:
        png = images.square_png(data, 64)  # Minecraft braucht genau 64×64
    except images.ImageError as exc:
        return page(ctx, "servers/appearance.html", server, 400, error=ctx.t(str(exc)),
                    has_icon=minecraft.icon_file(server_id).exists())
    path = minecraft.icon_file(server_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    ctx.conn.execute("UPDATE servers SET icon_path = ?, needs_restart = 1 WHERE id = ?", (path.name, server_id))
    raise Redirect(f"/server/{server_id}/darstellung?ok=icon")


@router.get("/server/{server_id}/icon.png")
def icon_png(server_id: int):
    path = minecraft.icon_file(server_id)
    if not path.exists():
        return FileResponse(Path(__file__).parent.parent / "static" / "favicon.svg", media_type="image/svg+xml")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})


# ---------- Spieler: Whitelist + Join-Verlauf ----------

def _players_page(ctx: Ctx, server, status_code: int = 200, **values):
    wl = ctx.conn.execute(
        "SELECT * FROM whitelist WHERE server_id = ? ORDER BY minecraft_name", (server["id"],)).fetchall()
    sessions = ctx.conn.execute(
        "SELECT * FROM player_sessions WHERE server_id = ? ORDER BY id DESC LIMIT 100", (server["id"],)).fetchall()
    return page(ctx, "servers/players.html", server, status_code, whitelist=wl, sessions=sessions, **values)


@router.get("/server/{server_id}/spieler", response_class=HTMLResponse)
def players(server_id: int, ctx: Ctx = Depends(get_ctx)):
    return _players_page(ctx, load(ctx, server_id))


@router.post("/server/{server_id}/whitelist")
def whitelist(server_id: int, action: str = Form(...), name: str = Form(""), csrf: str = Form(""),
              ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    name = name.strip()
    commands = []
    if action in ("on", "off"):
        ctx.conn.execute("UPDATE servers SET whitelist_enabled = ? WHERE id = ?", (int(action == "on"), server_id))
        commands = ["whitelist on" if action == "on" else "whitelist off"]
    elif action in ("add", "remove"):
        if not console.valid_mc_name(name):
            return _players_page(ctx, server, 400, error=ctx.t("Ungültiger Minecraft-Name (3–16 Zeichen: Buchstaben, Zahlen, _)."))
        if action == "add":
            ctx.conn.execute("INSERT OR IGNORE INTO whitelist (server_id, minecraft_name) VALUES (?, ?)", (server_id, name))
        else:
            ctx.conn.execute("DELETE FROM whitelist WHERE server_id = ? AND minecraft_name = ?", (server_id, name))
        commands = [f"whitelist {action} {name}"]
    if commands and is_active(server):
        db.add_job(ctx.conn, "rcon", server_id, ctx.user["id"], {"commands": commands})
    raise Redirect(f"/server/{server_id}/spieler")


# ---------- Miete: Verlängern, Auto-Verlängern, Reaktivieren, Löschen ----------

def _rent_page(ctx: Ctx, server, status_code: int = 200, **values):
    m = servers.model(ctx.conn, server["model_id"])
    examples = [(d, servers.price_for(ctx.conn, m, d)) for d in (7, 14, 30)]
    return page(ctx, "servers/rent.html", server, status_code, refund=servers.refund_amount(server),
                examples=examples, request_id=secrets.token_urlsafe(16),
                available=servers.availability(ctx.conn, m), **values)


@router.get("/server/{server_id}/miete", response_class=HTMLResponse)
def rent(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    msg = {"ext": "Verlängert.", "react": "Server wird reaktiviert …"}.get(ctx.request.query_params.get("ok", ""))
    return _rent_page(ctx, server, success=ctx.t(msg) if msg else None)


@router.post("/server/{server_id}/verlaengern")
def extend(server_id: int, days: int = Form(...), request_id: str = Form(""), csrf: str = Form(""),
           ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    try:
        with db.transaction(ctx.conn):
            servers.extend(ctx.conn, server, days, ctx.user["id"], request_id=request_id[:64] or None)
    except servers.ServerError as exc:
        return _rent_page(ctx, server, 400, error=ctx.t(exc.message))
    raise Redirect(f"/server/{server_id}/miete?ok=ext")


@router.post("/server/{server_id}/reaktivieren")
def reactivate(server_id: int, days: int = Form(...), request_id: str = Form(""), csrf: str = Form(""),
               ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    try:
        with db.transaction(ctx.conn):
            servers.reactivate(ctx.conn, server, days, ctx.user["id"], request_id=request_id[:64] or None)
    except servers.ServerError as exc:
        return _rent_page(ctx, server, 400, error=ctx.t(exc.message))
    raise Redirect(f"/server/{server_id}/miete?ok=react")


@router.post("/server/{server_id}/auto-verlaengern")
def auto_renew(server_id: int, enabled: str = Form("0"), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    load(ctx, server_id)
    ctx.check_csrf(csrf)
    ctx.conn.execute("UPDATE servers SET auto_renew = ? WHERE id = ?", (int(enabled == "1"), server_id))
    raise Redirect(f"/server/{server_id}/miete")


@router.post("/server/{server_id}/loeschen")
def delete(server_id: int, confirm_name: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    if confirm_name.strip() != server["name"]:
        return _rent_page(ctx, server, 400, error_delete=ctx.t("Bitte den Servernamen genau eintippen."))
    with db.transaction(ctx.conn):
        server = ctx.conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
        amount = servers.delete(ctx.conn, server, ctx.user["id"], with_refund=True)
        db.notify(ctx.conn, server["owner_id"], "deleted",
                  f"„{server['name']}“ wurde gelöscht. Erstattung: {amount} Coins.", server_id)
    raise Redirect("/server")


# ---------- Download ----------

@router.post("/server/{server_id}/download")
def request_download(server_id: int, part: str = Form("world"), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    server = load(ctx, server_id)
    ctx.check_csrf(csrf)
    pending = ctx.conn.execute(
        "SELECT 1 FROM jobs WHERE server_id = ? AND kind = 'download' AND status IN ('pending', 'running')", (server_id,)
    ).fetchone()
    if not pending and server["state"] in ("active", "archived"):
        db.add_job(ctx.conn, "download", server_id, ctx.user["id"], {"part": "world" if part == "world" else "all"})
    raise Redirect(f"/server/{server_id}#download")


@router.get("/download/{job_id}")
def download(job_id: int, ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    job = ctx.conn.execute("SELECT * FROM jobs WHERE id = ? AND kind = 'download' AND status = 'done'", (job_id,)).fetchone()
    if job is None:
        raise HTTPException(404)
    server = ctx.conn.execute("SELECT * FROM servers WHERE id = ?", (job["server_id"],)).fetchone()
    if server is None or not ctx.can_manage(server):
        raise HTTPException(404)
    path = (config.DOWNLOADS_DIR / (job["result"] or "")).resolve()
    if path.parent != config.DOWNLOADS_DIR.resolve() or not path.exists():
        raise HTTPException(404)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in server["name"])[:40] or "server"
    part = "welt" if path.name.endswith("-world.zip") else "dateien"
    return FileResponse(path, media_type="application/zip", filename=f"{safe}-{part}.zip")
