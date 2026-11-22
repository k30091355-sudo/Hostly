"""Öffentliche Seiten: Startseite mit Warnungen und Meldungen."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(ctx: Ctx = Depends(get_ctx)):
    if ctx.user is not None and not ctx.user["onboarded"]:
        raise Redirect("/willkommen")
    welcome = ctx.request.query_params.get("msg") == "welcome" and ctx.user is not None
    warnings, notes = [], []
    if ctx.user:
        # Ablauf-Warnung ab 3 Tage vorher
        warnings = ctx.conn.execute(
            """SELECT id, name, rented_until, auto_renew FROM servers
               WHERE owner_id = ? AND state = 'active' AND rented_until <= datetime('now', '+3 days')
               ORDER BY rented_until""",
            (ctx.user["id"],),
        ).fetchall()
        notes = ctx.conn.execute(
            "SELECT * FROM notifications WHERE user_id = ? AND read_at IS NULL ORDER BY id DESC LIMIT 10",
            (ctx.user["id"],),
        ).fetchall()
    from ... import servers
    from .events import home_events
    free = [m["name"] for m in servers.models(ctx.conn) if servers.availability(ctx.conn, m)]
    capacity_text = (ctx.t("Gerade ist Platz frei für: {models}", models=", ".join(ctx.t(n) for n in free))
                     if free else ctx.t("Gerade ist alles belegt – du kannst dich beim Kaufen vormerken lassen."))
    forecast = servers.renew_forecast(ctx.conn, ctx.user["id"]) if ctx.user else None
    return ctx.render("home.html", welcome=welcome, warnings=warnings, notes=notes, capacity_text=capacity_text,
                      forecast=forecast, **home_events(ctx))


@router.post("/meldung/{note_id}")
def dismiss(note_id: int, csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    ctx.conn.execute("UPDATE notifications SET read_at = datetime('now') WHERE id = ? AND user_id = ?",
                     (note_id, ctx.user["id"]))
    raise Redirect("/")


@router.get("/sw.js")
def service_worker():
    """Service-Worker muss unter / liegen, damit er für die ganze Seite gilt."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    return FileResponse(Path(__file__).parent.parent / "static" / "js" / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


@router.get("/version")
def version():
    """Aktuelle Hostly-Version (für den Hinweis „Neue Version – Seite aktualisieren“). Nie zwischenspeichern."""
    from fastapi.responses import JSONResponse
    from ... import config
    return JSONResponse({"version": config.VERSION}, headers={"Cache-Control": "no-store"})


@router.get("/offline", response_class=HTMLResponse)
def offline(ctx: Ctx = Depends(get_ctx)):
    return ctx.render("offline.html")


# ---------- Einführung für neue Spieler (Version 1.3.0) ----------

@router.get("/willkommen", response_class=HTMLResponse)
def welcome_tour(ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    from ... import coins
    return ctx.render("welcome.html", balance=coins.balance(ctx.conn, ctx.user["id"]))


@router.post("/willkommen")
def welcome_done(next: str = Form("/"), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    ctx.conn.execute("UPDATE users SET onboarded = 1 WHERE id = ?", (ctx.user["id"],))
    raise Redirect(next if next in ("/", "/code", "/kaufen") else "/")
