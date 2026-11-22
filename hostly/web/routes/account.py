"""Einstellungen: Passwort, Benutzername, Sprache, Design."""
import sqlite3

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, Response

from ... import config, db, security
from ..deps import Ctx, Redirect, get_ctx
from .auth import _username_taken, safe_next

router = APIRouter()

# Erfolgsmeldungen, die per ?msg=... angezeigt werden dürfen
MESSAGES = {"password": "settings.saved_password", "username": "settings.saved_username",
            "display": "settings.saved_display"}


def _page(ctx: Ctx, status_code: int = 200, **values):
    msg = ctx.request.query_params.get("msg")
    if msg in MESSAGES and "success" not in values:
        values["success"] = ctx.t(MESSAGES[msg])
    return ctx.render("settings.html", status_code=status_code, **values)


@router.get("/einstellungen", response_class=HTMLResponse)
def settings_page(ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    return _page(ctx)


@router.post("/einstellungen/passwort")
def change_password(
    old_password: str = Form(""), new_password: str = Form(""), new_password2: str = Form(""),
    csrf: str = Form(""), ctx: Ctx = Depends(get_ctx),
):
    ctx.require_login()
    ctx.check_csrf(csrf)
    if not security.verify_password(ctx.user["password_hash"], old_password):
        return _page(ctx, 400, error_password=ctx.t("err.old_password_wrong"))
    error = security.check_password(new_password, new_password2)
    if error is None and new_password == old_password:
        error = "err.password_same"
    if error:
        return _page(ctx, 400, error_password=ctx.t(error))

    with db.transaction(ctx.conn):
        ctx.conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (security.hash_password(new_password), ctx.user["id"]),
        )
        security.delete_other_sessions(ctx.conn, ctx.user["id"], ctx.session["id"])
        db.audit(ctx.conn, ctx.user["id"], "password_changed")
    raise Redirect("/einstellungen?msg=password")


@router.post("/einstellungen/benutzername")
def change_username(
    username: str = Form(""), password: str = Form(""),
    csrf: str = Form(""), ctx: Ctx = Depends(get_ctx),
):
    ctx.require_login()
    ctx.check_csrf(csrf)
    username = username.strip()
    if not security.verify_password(ctx.user["password_hash"], password):
        return _page(ctx, 400, error_username=ctx.t("err.old_password_wrong"), new_username=username)
    error = security.check_username(username)
    if error is None and _username_taken(ctx.conn, username, except_id=ctx.user["id"]):
        error = "err.username_taken"
    if error:
        return _page(ctx, 400, error_username=ctx.t(error), new_username=username)

    try:
        with db.transaction(ctx.conn):
            ctx.conn.execute("UPDATE users SET username = ? WHERE id = ?", (username, ctx.user["id"]))
            db.audit(ctx.conn, ctx.user["id"], "username_changed", f"{ctx.user['username']} -> {username}")
    except sqlite3.IntegrityError:
        return _page(ctx, 400, error_username=ctx.t("err.username_taken"), new_username=username)
    raise Redirect("/einstellungen?msg=username")


@router.post("/einstellungen/darstellung")
def change_display(
    language: str = Form("de"), theme: str = Form("system"),
    csrf: str = Form(""), ctx: Ctx = Depends(get_ctx),
):
    ctx.require_login()
    ctx.check_csrf(csrf)
    if language not in config.LANGUAGES or theme not in config.THEMES:
        raise Redirect("/einstellungen")
    ctx.conn.execute("UPDATE users SET language = ?, theme = ? WHERE id = ?", (language, theme, ctx.user["id"]))
    raise Redirect("/einstellungen?msg=display")


# ---------- Schnell-Umschalter in der Kopfleiste (geht auch ohne Login) ----------

def _save_choice(ctx: Ctx, column: str, cookie: str, value: str) -> None:
    if ctx.user:
        ctx.conn.execute(f"UPDATE users SET {column} = ? WHERE id = ?", (value, ctx.user["id"]))
    else:
        ctx.cookies[cookie] = (value, 60 * 60 * 24 * 365)


@router.post("/design")
def set_theme(theme: str = Form(...), back: str = Form("/"), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.check_csrf(csrf)
    if theme in config.THEMES:
        _save_choice(ctx, "theme", "hostly_theme", theme)
    if ctx.request.headers.get("x-requested-with") == "fetch":
        return Response(status_code=204)
    raise Redirect(safe_next(back))


@router.post("/sprache")
def set_language(language: str = Form(...), back: str = Form("/"), csrf: str = Form(""),
                 ctx: Ctx = Depends(get_ctx)):
    ctx.check_csrf(csrf)
    if language in config.LANGUAGES:
        _save_choice(ctx, "language", "hostly_lang", language)
    raise Redirect(safe_next(back))
