"""Registrieren, Login, Abmelden."""
import sqlite3

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from ... import coins, config, db, promotions, security
from ..deps import Ctx, Redirect, cookie_secure, get_ctx

router = APIRouter()


def safe_next(url: str | None) -> str:
    """Nur Weiterleitungen innerhalb von Hostly erlauben."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return "/"


def _login_and_redirect(ctx: Ctx, user_id: int, target: str):
    token = security.create_session(ctx.conn, user_id, ctx.ip, ctx.request.headers.get("user-agent"))
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        config.SESSION_COOKIE, token, max_age=config.SESSION_DAYS * 86400,
        httponly=True, samesite="lax", secure=cookie_secure(ctx.request),
    )
    return response


# ---------- Login ----------

@router.get("/login", response_class=HTMLResponse)
def login_page(next: str = "/", ctx: Ctx = Depends(get_ctx)):
    if ctx.user:
        raise Redirect(safe_next(next))
    return ctx.render("login.html", next=safe_next(next), username="")


@router.post("/login")
def login(
    username: str = Form(""), password: str = Form(""), next: str = Form("/"),
    csrf: str = Form(""), ctx: Ctx = Depends(get_ctx),
):
    ctx.check_csrf(csrf)
    username = username.strip()
    target = safe_next(next)

    def fail(key: str):
        return ctx.render("login.html", status_code=400, error=ctx.t(key), next=target, username=username)

    user = ctx.conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ? AND deleted_at IS NULL", (username,)
    ).fetchone()
    ok = security.verify_password(user["password_hash"] if user else None, password)
    security.record_login(ctx.conn, username, ctx.ip, ok)
    if not ok:
        return fail("err.login_wrong")

    if security.needs_rehash(user["password_hash"]):
        ctx.conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                         (security.hash_password(password), user["id"]))
    return _login_and_redirect(ctx, user["id"], target)


# ---------- Registrieren ----------

@router.get("/registrieren", response_class=HTMLResponse)
def register_page(ctx: Ctx = Depends(get_ctx)):
    if ctx.user:
        raise Redirect("/")
    return ctx.render("register.html", username="")


def _username_taken(conn: sqlite3.Connection, username: str, except_id: int | None = None) -> bool:
    row = conn.execute(
        "SELECT id FROM users WHERE username = ? AND deleted_at IS NULL AND id IS NOT ?",
        (username, except_id),
    ).fetchone()
    return row is not None


@router.get("/registrieren/name-pruefen", response_class=HTMLResponse)
def check_name(username: str = "", ctx: Ctx = Depends(get_ctx)):
    """Live-Prüfung beim Tippen (HTMX)."""
    username = username.strip()
    if not username:
        return HTMLResponse("")
    error = security.check_username(username)
    if error is None and _username_taken(ctx.conn, username):
        error = "err.username_taken"
    if error:
        return HTMLResponse(f'<span class="hint bad">{ctx.t(error)}</span>')
    return HTMLResponse(f'<span class="hint good">{ctx.t("register.name_free")}</span>')


@router.post("/registrieren")
def register(
    username: str = Form(""), password: str = Form(""), password2: str = Form(""),
    csrf: str = Form(""), ctx: Ctx = Depends(get_ctx),
):
    ctx.check_csrf(csrf)
    username = username.strip()
    error = security.check_username(username) or security.check_password(password, password2)
    if error is None and _username_taken(ctx.conn, username):
        error = "err.username_taken"
    if error:
        return ctx.render("register.html", status_code=400, error=ctx.t(error), username=username)

    password_hash = security.hash_password(password)
    try:
        with db.transaction(ctx.conn):
            # Der allererste Account wird automatisch Admin.
            cur = ctx.conn.execute(
                """INSERT INTO users (username, password_hash, language, theme, is_admin)
                   VALUES (?, ?, ?, ?, (SELECT COUNT(*) = 0 FROM users))""",
                (username, password_hash, ctx.lang, ctx.theme),
            )
            user_id = cur.lastrowid
            # Startbonus (Version 1.3.0) + Einführung für neue Spieler
            bonus = promotions.signup_bonus(ctx.conn)
            if bonus:
                coins.book(ctx.conn, user_id, bonus, "startbonus")
            ctx.conn.execute("UPDATE users SET onboarded = 0 WHERE id = ?", (user_id,))
            db.audit(ctx.conn, user_id, "register")
    except sqlite3.IntegrityError:  # gleichzeitig registriert
        return ctx.render("register.html", status_code=400, error=ctx.t("err.username_taken"), username=username)
    return _login_and_redirect(ctx, user_id, "/willkommen")


# ---------- Abmelden ----------

@router.post("/abmelden")
def logout(csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.check_csrf(csrf)
    security.delete_session(ctx.conn, ctx.request.cookies.get(config.SESSION_COOKIE))
    ctx.cookies[config.SESSION_COOKIE] = (None, 0)
    raise Redirect("/")
