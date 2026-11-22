"""Server kaufen: Vergleich, Vorlagen, Live-Preis, Nachtpause, Kauf, Vormerken."""
import secrets

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ... import config, db, extensions, modrinth, promotions, servers
from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()


def _shop(ctx: Ctx, status_code: int = 200, **values):
    models = servers.models(ctx.conn)
    available = {m["id"]: servers.availability(ctx.conn, m) for m in models}
    values.setdefault("form", {"model_id": models[1]["id"], "type": "PAPER", "days": 7, "name": "",
                               "template": "", "np_on": False, "np_start": 1, "np_end": 8, "public": False})
    form = values["form"]
    selected = next((m for m in models if m["id"] == form["model_id"]), models[0])
    days = form["days"] if not servers.check_days(form["days"]) else 1
    waiting = set()
    if ctx.user:
        waiting = {r[0] for r in ctx.conn.execute(
            "SELECT model_id FROM waitlist WHERE user_id = ? AND notified_at IS NULL", (ctx.user["id"],))}
    return ctx.render("shop.html", status_code=status_code, models=models, available=available,
                      types=config.SERVER_TYPES, request_id=secrets.token_urlsafe(16),
                      promo={m["id"]: servers.promo_percent(ctx.conn, m["id"]) for m in models},
                      ram_promo={m["id"]: promotions.ram_bonus(ctx.conn, m["id"])[0] for m in models},
                      templates=extensions.TEMPLATES, waiting=waiting,
                      price=servers.price_for(ctx.conn, selected, days), model=selected,
                      price_available=available[selected["id"]], **values)


@router.get("/kaufen", response_class=HTMLResponse)
def shop(ctx: Ctx = Depends(get_ctx)):
    return _shop(ctx)


@router.get("/kaufen/preis", response_class=HTMLResponse)
def live_price(model_id: int = 0, days: int = 1, verlaengern: int = 0, ctx: Ctx = Depends(get_ctx)):
    """Preis live berechnen (HTMX), ohne etwas zu ändern."""
    m = servers.model(ctx.conn, model_id)
    if m is None or servers.check_days(days):
        return HTMLResponse(f'<span class="hint bad">{ctx.t("Bitte zwischen 1 und 3650 Tagen wählen.")}</span>')
    price = servers.price_for(ctx.conn, m, days)
    return ctx.render("_price.html", price=price, model=m,
                      price_available=bool(verlaengern) or servers.availability(ctx.conn, m))


@router.post("/kaufen")
def buy(model_id: int = Form(...), server_type: str = Form("PAPER"), days: int = Form(...), name: str = Form(""),
        template: str = Form(""), np_on: str = Form(""), np_start: int = Form(1), np_end: int = Form(8),
        public: str = Form(""), request_id: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    name = name.strip()
    form = {"model_id": model_id, "type": server_type, "days": days, "name": name, "template": template,
            "np_on": bool(np_on), "np_start": np_start, "np_end": np_end, "public": bool(public)}
    mc_version, entries = "LATEST", []
    tpl = extensions.TEMPLATES.get(template)
    if tpl:
        server_type = tpl["type"]
        try:
            mc_version, entries = extensions.pick_template_version(template)
        except (extensions.ExtensionError, modrinth.ModrinthError) as exc:
            return _shop(ctx, 400, error=ctx.t(getattr(exc, "message", None) or str(exc)), form=form)
    try:
        with db.transaction(ctx.conn):
            server_id = servers.purchase(
                ctx.conn, ctx.user["id"], model_id, server_type, days, name, request_id=request_id[:64] or None,
                night_pause=(np_start, np_end) if np_on else None, public_listed=bool(public),
                template=template if tpl else None, mc_version=mc_version)
            if entries:
                extensions.add_entries(ctx.conn, server_id, entries)
    except servers.ServerError as exc:
        return _shop(ctx, 400, error=ctx.t(exc.message), form=form)
    raise Redirect(f"/server/{server_id}?neu=1")


@router.post("/kaufen/vormerken")
def waitlist(model_id: int = Form(...), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    """„Benachrichtige mich, wenn Platz frei ist“"""
    ctx.require_login()
    ctx.check_csrf(csrf)
    if servers.model(ctx.conn, model_id):
        ctx.conn.execute(
            """INSERT INTO waitlist (user_id, model_id) VALUES (?, ?)
               ON CONFLICT(user_id, model_id) DO UPDATE SET notified_at = NULL, created_at = datetime('now')""",
            (ctx.user["id"], model_id))
    raise Redirect("/kaufen?vorgemerkt=1")
