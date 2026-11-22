"""Öffentliche Seiten: Startseite mit Warnungen und Meldungen."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(ctx: Ctx = Depends(get_ctx)):
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
    return ctx.render("home.html", welcome=welcome, warnings=warnings, notes=notes, capacity_text=capacity_text,
                      **home_events(ctx))


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


@router.get("/offline", response_class=HTMLResponse)
def offline(ctx: Ctx = Depends(get_ctx)):
    return ctx.render("offline.html")
