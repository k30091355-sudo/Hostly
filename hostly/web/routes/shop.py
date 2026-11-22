"""Server kaufen: Vergleich, Live-Preis, Kauf."""
import secrets

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ... import config, db, servers
from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()


def _shop(ctx: Ctx, status_code: int = 200, **values):
    models = servers.models(ctx.conn)
    available = {m["id"]: servers.availability(ctx.conn, m) for m in models}
    values.setdefault("form", {"model_id": models[1]["id"], "type": "PAPER", "days": 7, "name": ""})
    form = values["form"]
    selected = next((m for m in models if m["id"] == form["model_id"]), models[0])
    days = form["days"] if not servers.check_days(form["days"]) else 1
    values.update(price=servers.price_for(ctx.conn, selected, days), model=selected,
                  price_available=available[selected["id"]])
    return ctx.render("shop.html", status_code=status_code, models=models, available=available,
                      types=config.SERVER_TYPES, request_id=secrets.token_urlsafe(16),
                      promo={m["id"]: servers.promo_percent(ctx.conn, m["id"]) for m in models}, **values)


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
    return ctx.render("_price.html", price=price, model=m, price_available=bool(verlaengern) or servers.availability(ctx.conn, m))


@router.post("/kaufen")
def buy(model_id: int = Form(...), server_type: str = Form(...), days: int = Form(...), name: str = Form(""),
        request_id: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    name = name.strip()
    form = {"model_id": model_id, "type": server_type, "days": days, "name": name}
    try:
        with db.transaction(ctx.conn):
            server_id = servers.purchase(ctx.conn, ctx.user["id"], model_id, server_type, days, name,
                                         request_id=request_id[:64] or None)
    except servers.ServerError as exc:
        return _shop(ctx, 400, error=ctx.t(exc.message), form=form)
    raise Redirect(f"/server/{server_id}?neu=1")
