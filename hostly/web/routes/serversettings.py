"""Reiter „Einstellungen“: Spiel-Einstellungen, Gamerules, neue Welt (Version 1.3.0)."""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ... import db, gamesettings as gs
from ..deps import Ctx, Redirect, get_ctx
from .myservers import busy_job, is_active, load, page

router = APIRouter()


def _active(ctx: Ctx, server_id: int):
    server = load(ctx, server_id)
    if not is_active(server):
        raise Redirect(f"/server/{server_id}")
    return server


@router.get("/server/{server_id}/einstellungen", response_class=HTMLResponse)
def settings_page(server_id: int, ctx: Ctx = Depends(get_ctx)):
    server = _active(ctx, server_id)
    return page(ctx, "servers/settings.html", server, rules=gs.load_rules(server), gs=gs,
                ok=ctx.request.query_params.get("ok"))


@router.post("/server/{server_id}/einstellungen")
async def save_settings(server_id: int, request: Request, ctx: Ctx = Depends(get_ctx)):
    server = _active(ctx, server_id)
    form = await request.form()
    ctx.check_csrf(str(form.get("csrf", "")))
    difficulty = str(form.get("difficulty", "easy"))
    gamemode = str(form.get("gamemode", "survival"))
    ctx.conn.execute(
        """UPDATE servers SET difficulty = ?, gamemode = ?, pvp = ?, allow_flight = ?, view_distance = ?,
           spawn_protection = ?, needs_restart = 1 WHERE id = ?""",
        (difficulty if difficulty in gs.DIFFICULTIES else "easy",
         gamemode if gamemode in gs.GAMEMODES else "survival",
         int(bool(form.get("pvp"))), int(bool(form.get("allow_flight"))),
         gs.clamp(form.get("view_distance"), gs.VIEW_DISTANCE, 8),
         gs.clamp(form.get("spawn_protection"), gs.SPAWN_PROTECTION, 16), server_id))
    # PvP ist ab Minecraft 26.x auch eine Gamerule – gleich mitsetzen
    rules = gs.changed_rules(server)
    if bool(form.get("pvp")) != rules.get("pvp", True):
        rules["pvp"] = bool(form.get("pvp"))
        ctx.conn.execute("UPDATE servers SET gamerules = ? WHERE id = ?", (json.dumps(rules), server_id))
    db.audit(ctx.conn, ctx.user["id"], "server_settings", f"Server {server_id}")
    raise Redirect(f"/server/{server_id}/einstellungen?ok=1")


@router.post("/server/{server_id}/gamerules")
async def save_gamerules(server_id: int, request: Request, ctx: Ctx = Depends(get_ctx)):
    server = _active(ctx, server_id)
    form = await request.form()
    ctx.check_csrf(str(form.get("csrf", "")))
    rules = gs.changed_rules(server)
    for key in gs.GAMERULES:
        rules[key] = bool(form.get(key))
    rules[gs.SLEEP_RULE[0]] = gs.clamp(form.get(gs.SLEEP_RULE[0]), (0, 100), 100)
    ctx.conn.execute("UPDATE servers SET gamerules = ? WHERE id = ?", (json.dumps(rules), server_id))
    if not ctx.conn.execute("SELECT 1 FROM jobs WHERE server_id = ? AND kind = 'gamerules' AND status = 'pending'",
                            (server_id,)).fetchone():
        db.add_job(ctx.conn, "gamerules", server_id, ctx.user["id"])
    raise Redirect(f"/server/{server_id}/einstellungen?ok=2")


@router.post("/server/{server_id}/neue-welt")
async def new_world(server_id: int, request: Request, ctx: Ctx = Depends(get_ctx)):
    server = _active(ctx, server_id)
    form = await request.form()
    ctx.check_csrf(str(form.get("csrf", "")))
    if not form.get("confirm"):
        return page(ctx, "servers/settings.html", server, 400, rules=gs.load_rules(server), gs=gs,
                    error=ctx.t("Bitte bestätige, dass die alte Welt gelöscht werden darf."))
    if busy_job(ctx, server_id) is None:
        db.add_job(ctx.conn, "world_reset", server_id, ctx.user["id"],
                   {"seed": str(form.get("seed", "")).strip()[:64]})
        db.audit(ctx.conn, ctx.user["id"], "world_reset", f"Server {server_id}")
    raise Redirect(f"/server/{server_id}")
