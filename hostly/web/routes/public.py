"""Öffentliche Serverliste und Statistiken per Kürzel (Stufe 8b)."""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from ... import stats
from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()


@router.get("/serverliste", response_class=HTMLResponse)
def server_list(ctx: Ctx = Depends(get_ctx)):
    """Nur Server mit „öffentlich“ = an. Liest nur gespeicherten Status – weckt nie einen Server."""
    rows = ctx.conn.execute(
        """SELECT s.id, s.name, s.motd, s.short_code, s.type, s.mc_version, t.public_address, m.max_players,
                  st.running, st.paused, st.players_online
           FROM servers s JOIN models m ON m.id = s.model_id LEFT JOIN tunnels t ON t.id = s.tunnel_id
           LEFT JOIN server_status st ON st.server_id = s.id
           WHERE s.public_listed = 1 AND s.whitelist_enabled = 0 AND s.state = 'active' ORDER BY st.players_online DESC, s.id"""
    ).fetchall()
    return ctx.render("serverlist.html", rows=rows)


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
    return ctx.render("stats.html", server=server, st=st, data=data, exts=exts,
                      chart24=stats.chart(data["samples"], 24, server["max_players"]),
                      chart7=stats.chart(data["samples"], 24 * 7, server["max_players"]))


