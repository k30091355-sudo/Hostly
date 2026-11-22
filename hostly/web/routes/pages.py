"""Öffentliche Seiten."""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from ..deps import Ctx, get_ctx

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(ctx: Ctx = Depends(get_ctx)):
    welcome = ctx.request.query_params.get("msg") == "welcome" and ctx.user is not None
    return ctx.render("home.html", welcome=welcome)
