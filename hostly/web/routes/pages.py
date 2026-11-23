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
    extra = _my_home(ctx) if ctx.user else _guest_home(ctx)
    return ctx.render("home.html", welcome=welcome, warnings=warnings, notes=notes, capacity_text=capacity_text,
                      free_models=[ctx.t(n) for n in free], forecast=forecast, live_running=_running_count(ctx.conn),
                      public_servers=_public_servers(ctx.conn), **extra, **home_events(ctx))


# ---------- Startseite (Version 1.4.0) ----------

MODEL_ICONS = {"holz": "🪵", "eisen": "⚙️", "diamant": "💎"}


def _running_count(conn) -> int:
    """Wie viele Server gerade an sind (aus dem gespeicherten Status – weckt nichts)."""
    return conn.execute(
        """SELECT COUNT(*) FROM servers s JOIN server_status st ON st.server_id = s.id
           WHERE s.state = 'active' AND st.running = 1""").fetchone()[0]


def _public_servers(conn) -> list:
    return conn.execute(
        """SELECT s.name, s.short_code, s.whitelist_enabled, st.running, st.paused, st.players_online
           FROM servers s LEFT JOIN server_status st ON st.server_id = s.id
           WHERE s.public_listed = 1 AND s.state = 'active'
           ORDER BY COALESCE(st.players_online, 0) DESC, s.id LIMIT 5""").fetchall()


def _guest_home(ctx: Ctx) -> dict:
    """Besucher: Live-Zahlen und die Modelle. Keine Namen von Nutzern (Hostly ist anonym)."""
    from ... import promotions, servers
    conn = ctx.conn
    players_today = conn.execute(
        "SELECT COUNT(DISTINCT lower(minecraft_name)) FROM player_sessions WHERE joined_at >= datetime('now', '-1 day')"
    ).fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM servers WHERE state = 'active'").fetchone()[0]
    counts = dict(conn.execute("SELECT model_id, COUNT(*) FROM servers WHERE state = 'active' GROUP BY model_id").fetchall())
    popular = max(counts, key=counts.get) if counts else None
    models = [{"m": m, "icon": MODEL_ICONS.get(m["key"], "🖥️"), "popular": m["id"] == popular}
              for m in servers.models(conn)]
    return {"players_today": players_today, "servers_active": active, "models": models,
            "signup_bonus": promotions.signup_bonus(conn)}


def _my_home(ctx: Ctx) -> dict:
    """Eingeloggt: eigene Server als Karten + „Was ist passiert?“."""
    from ... import servers
    conn, uid = ctx.conn, ctx.user["id"]
    rows = conn.execute(
        """SELECT s.*, m.name AS model_name, m.key AS model_key, m.max_players, t.public_address,
                  st.running, st.paused, st.health, st.players_online, st.players_max
           FROM servers s JOIN models m ON m.id = s.model_id LEFT JOIN tunnels t ON t.id = s.tunnel_id
           LEFT JOIN server_status st ON st.server_id = s.id
           WHERE s.owner_id = ? AND s.state != 'deleted' ORDER BY s.state = 'archived', s.id DESC""", (uid,)).fetchall()
    my = []
    for r in rows:
        label, cls = servers.display_status(r, r if r["running"] is not None else None,
                                            servers.night_pause_running(conn, r["id"]) is not None)
        my.append({"server": r, "label": label, "cls": cls, "icon": MODEL_ICONS.get(r["model_key"], "🖥️")})
    feed = []
    for j in conn.execute(
            """SELECT p.minecraft_name, p.joined_at, s.id, s.name FROM player_sessions p JOIN servers s ON s.id = p.server_id
               WHERE s.owner_id = ? AND p.joined_at >= datetime('now', '-1 day') ORDER BY p.joined_at DESC LIMIT 5""",
            (uid,)):
        feed.append({"at": j["joined_at"], "icon": "🟢", "link": f"/server/{j['id']}/spieler",
                     "text": ctx.t("{player} ist „{server}“ beigetreten", player=j["minecraft_name"], server=j["name"])})
    for q in conn.execute(
            """SELECT r.minecraft_name, r.created_at, s.id FROM whitelist_requests r JOIN servers s ON s.id = r.server_id
               WHERE s.owner_id = ? AND r.status = 'offen' ORDER BY r.id DESC LIMIT 5""", (uid,)):
        feed.append({"at": q["created_at"], "icon": "🔒", "link": f"/server/{q['id']}/spieler",
                     "button": ctx.t("Ansehen"),
                     "text": ctx.t("Whitelist-Anfrage von {player}", player=q["minecraft_name"])})
    feed.sort(key=lambda f: f["at"], reverse=True)
    return {"my_servers": my, "feed": feed[:6]}


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
