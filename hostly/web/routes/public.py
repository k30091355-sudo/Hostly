"""Öffentliche Serverliste und Statistiken per Kürzel (Stufe 8b)."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ... import console, db, stats
from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()


@router.get("/serverliste", response_class=HTMLResponse)
def server_list(ctx: Ctx = Depends(get_ctx)):
    """Nur Server mit „öffentlich“ = an. Liest nur gespeicherten Status – weckt nie einen Server."""
    rows = ctx.conn.execute(
        """SELECT s.id, s.name, s.motd, s.short_code, s.type, s.mc_version, s.whitelist_enabled, t.public_address, m.max_players,
                  st.running, st.paused, st.players_online
           FROM servers s JOIN models m ON m.id = s.model_id LEFT JOIN tunnels t ON t.id = s.tunnel_id
           LEFT JOIN server_status st ON st.server_id = s.id
           WHERE s.public_listed = 1 AND s.state = 'active' ORDER BY st.players_online DESC, s.id"""
    ).fetchall()
    from ... import extensions
    modpacks = {r["id"] for r in ctx.conn.execute("SELECT * FROM servers WHERE public_listed = 1 AND state = 'active'")
                if extensions.has_modpack(ctx.conn, r)}
    return ctx.render("serverlist.html", rows=rows, modpacks=modpacks)


@router.get("/statistik", response_class=HTMLResponse)
def stats_lookup(code: str = "", ctx: Ctx = Depends(get_ctx)):
    code = code.strip().lower()
    if code:
        raise Redirect(f"/s/{code}")
    return ctx.render("stats_lookup.html")


@router.get("/s/{code}", response_class=HTMLResponse)
def server_stats(code: str, ctx: Ctx = Depends(get_ctx)):
    server = ctx.conn.execute(
        """SELECT s.*, m.name AS model_name, m.max_players, t.public_address FROM servers s
           JOIN models m ON m.id = s.model_id LEFT JOIN tunnels t ON t.id = s.tunnel_id
           WHERE s.short_code = ? AND s.state != 'deleted'""", (code.lower(),)).fetchone()
    if server is None:
        return ctx.render("stats_lookup.html", status_code=404, error=ctx.t("Kein Server mit diesem Kürzel gefunden."))
    st = ctx.conn.execute("SELECT * FROM server_status WHERE server_id = ?", (server["id"],)).fetchone()
    data = stats.server_stats(ctx.conn, server["id"])
    exts = ctx.conn.execute(
        "SELECT title, kind FROM server_extensions WHERE server_id = ? AND enabled = 1 AND is_dependency = 0 ORDER BY title",
        (server["id"],)).fetchall()
    my_request = on_list = None
    if ctx.user is not None and server["whitelist_enabled"]:
        my_request = ctx.conn.execute(
            "SELECT * FROM whitelist_requests WHERE server_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
            (server["id"], ctx.user["id"])).fetchone()
        if ctx.user["minecraft_name"]:
            on_list = ctx.conn.execute("SELECT 1 FROM whitelist WHERE server_id = ? AND minecraft_name = ?",
                                       (server["id"], ctx.user["minecraft_name"])).fetchone()
    from ... import extensions
    return ctx.render("stats.html", server=server, st=st, data=data, exts=exts, my_request=my_request,
                      modpack=extensions.has_modpack(ctx.conn, server),
                      on_list=on_list, sent=ctx.request.query_params.get("anfrage"),
                      chart24=stats.chart(data["samples"], 24, server["max_players"]),
                      chart7=stats.chart(data["samples"], 24 * 7, server["max_players"]))




@router.post("/s/{code}/anfrage")
def whitelist_request(code: str, minecraft_name: str = Form(""), message: str = Form(""), csrf: str = Form(""),
                      ctx: Ctx = Depends(get_ctx)):
    """Whitelist-Anfrage an den Besitzer (Version 1.3.0). Nur eingeloggt, höchstens eine offene pro Server."""
    ctx.require_login()
    ctx.check_csrf(csrf)
    server = ctx.conn.execute("SELECT * FROM servers WHERE short_code = ? AND state = 'active'",
                              (code.lower(),)).fetchone()
    if server is None or not server["whitelist_enabled"]:
        raise Redirect(f"/s/{code}")
    name = minecraft_name.strip()
    if not console.valid_mc_name(name):
        raise Redirect(f"/s/{code}?anfrage=name#anfrage")
    open_req = ctx.conn.execute(
        "SELECT 1 FROM whitelist_requests WHERE server_id = ? AND user_id = ? AND status = 'offen'",
        (server["id"], ctx.user["id"])).fetchone()
    if not open_req and server["owner_id"] != ctx.user["id"]:
        ctx.conn.execute(
            "INSERT INTO whitelist_requests (server_id, user_id, minecraft_name, message) VALUES (?, ?, ?, ?)",
            (server["id"], ctx.user["id"], name, message.strip()[:200] or None))
        db.notify(ctx.conn, server["owner_id"], "whitelist",
                  f"{name} möchte auf die Whitelist von „{server['name']}“. Annehmen im Reiter „Spieler“.", server["id"])
    raise Redirect(f"/s/{code}?anfrage=ok#anfrage")
