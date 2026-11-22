"""Code einlösen und Coin-Verlauf."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ... import codes, coins, db
from ..deps import Ctx, get_ctx

router = APIRouter()


@router.get("/code", response_class=HTMLResponse)
def redeem_page(ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    return ctx.render("code.html", code="")


@router.post("/code")
def redeem(code: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    try:
        with db.transaction(ctx.conn):
            amount = codes.redeem(ctx.conn, ctx.user["id"], code)
    except codes.RedeemError as exc:
        return ctx.render("code.html", status_code=400, error=ctx.t(exc.message), code=code)
    ctx.cache.pop("balance", None)
    return ctx.render("code.html", success=ctx.t("+{coins} Coins gutgeschrieben 🎉", coins=amount), code="")


@router.get("/einstellungen/coins", response_class=HTMLResponse)
def history(ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    rows = ctx.conn.execute(
        "SELECT * FROM coin_ledger WHERE user_id = ? ORDER BY id DESC LIMIT 500", (ctx.user["id"],)
    ).fetchall()
    return ctx.render("coins.html", rows=rows, reasons=coins.REASONS)
