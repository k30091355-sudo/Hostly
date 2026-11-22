"""Einstellungen: Passwort, Benutzername, Sprache, Design."""
import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from ... import config, console, db, images, security
from ..deps import Ctx, Redirect, get_ctx
from .auth import _username_taken, safe_next

router = APIRouter()

# Erfolgsmeldungen, die per ?msg=... angezeigt werden dürfen
MESSAGES = {"password": "settings.saved_password", "username": "settings.saved_username",
            "display": "settings.saved_display", "minecraft": "settings.saved_display",
            "avatar": "settings.saved_display"}


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
    new_password: str = Form(""), new_password2: str = Form(""),
    csrf: str = Form(""), ctx: Ctx = Depends(get_ctx),
):
    """Neues Passwort setzen – das aktuelle Passwort wird nicht abgefragt (Entscheidung des Besitzers)."""
    ctx.require_login()
    ctx.check_csrf(csrf)
    error = security.check_password(new_password, new_password2)
    if error is None and ctx.user["must_change_password"] and security.verify_password(ctx.user["password_hash"], new_password):
        error = "err.password_same"   # das zufällige Admin-Passwort darf nicht einfach behalten werden
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


# ---------- Minecraft-Name (→ automatisch OP) ----------

@router.post("/einstellungen/minecraft")
def set_minecraft_name(minecraft_name: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    name = minecraft_name.strip()
    if name and not console.valid_mc_name(name):
        return _page(ctx, 400, error_minecraft=ctx.t("Ungültiger Minecraft-Name (3–16 Zeichen: Buchstaben, Zahlen, _)."))
    with db.transaction(ctx.conn):
        ctx.conn.execute("UPDATE users SET minecraft_name = ? WHERE id = ?", (name or None, ctx.user["id"]))
        if name:
            # auf allen eigenen laufenden Servern sofort OP geben
            for row in ctx.conn.execute(
                    "SELECT id FROM servers WHERE owner_id = ? AND state = 'active'", (ctx.user["id"],)).fetchall():
                db.add_job(ctx.conn, "rcon", row["id"], ctx.user["id"], {"commands": [f"op {name}"]})
    raise Redirect("/einstellungen?msg=minecraft")


# ---------- Profilbild ----------

def avatar_file(user_id: int):
    return config.UPLOADS_DIR / "avatars" / f"{user_id}.png"


@router.post("/einstellungen/profilbild")
async def set_avatar(mode: str = Form("none"), image: UploadFile | None = File(None), csrf: str = Form(""),
                     ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    if mode == "own":
        data = await image.read(images.MAX_UPLOAD_BYTES + 1) if image else b""
        try:
            png = images.square_png(data, 128)
        except images.ImageError as exc:
            return _page(ctx, 400, error_avatar=ctx.t(str(exc)))
        path = avatar_file(ctx.user["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
    elif mode == "minecraft":
        if not ctx.user["minecraft_name"]:
            return _page(ctx, 400, error_avatar=ctx.t("Bitte zuerst deinen Minecraft-Namen eintragen."))
    else:
        mode = "none"
    ctx.conn.execute("UPDATE users SET avatar_mode = ?, avatar_version = avatar_version + 1 WHERE id = ?",
                     (mode, ctx.user["id"]))
    raise Redirect("/einstellungen?msg=avatar")


@router.get("/profilbild/{user_id}.png")
def avatar(user_id: int):
    path = avatar_file(user_id)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


# ---------- Coins übertragen, Account löschen (Stufe 6) ----------

@router.post("/einstellungen/coins-uebertragen")
def transfer_coins(username: str = Form(""), amount: int = Form(0), password: str = Form(""), csrf: str = Form(""),
                   ctx: Ctx = Depends(get_ctx)):
    from ... import servers

    ctx.require_login()
    ctx.check_csrf(csrf)
    if not security.verify_password(ctx.user["password_hash"], password):
        return _page(ctx, 400, error_transfer=ctx.t("err.old_password_wrong"))
    try:
        with db.transaction(ctx.conn):
            to = servers.transfer_coins(ctx.conn, ctx.user["id"], username, amount)
    except servers.ServerError as exc:
        return _page(ctx, 400, error_transfer=ctx.t(exc.message))
    ctx.cache.pop("balance", None)
    return _page(ctx, success=ctx.t("{n} Coins an {name} übertragen.", n=amount, name=to["username"]))


@router.post("/einstellungen/account-loeschen")
def delete_account(password: str = Form(""), confirm: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    """Alle Server (auch Archive) und Coins werden gelöscht, der Benutzername wird wieder frei."""
    from ... import coins as coins_mod, servers

    ctx.require_login()
    ctx.check_csrf(csrf)
    if not security.verify_password(ctx.user["password_hash"], password) or confirm != "1":
        return _page(ctx, 400, error_delete=ctx.t("Bitte Passwort eingeben und bestätigen."))
    uid = ctx.user["id"]
    with db.transaction(ctx.conn):
        for server in ctx.conn.execute("SELECT * FROM servers WHERE owner_id = ? AND state != 'deleted'", (uid,)).fetchall():
            servers.delete(ctx.conn, server, uid, with_refund=False)
        rest = coins_mod.balance(ctx.conn, uid)
        if rest:
            coins_mod.book(ctx.conn, uid, -rest, "account_geloescht")
        ctx.conn.execute("UPDATE users SET deleted_at = datetime('now'), is_admin = 0, minecraft_name = NULL WHERE id = ?", (uid,))
        ctx.conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        ctx.conn.execute("DELETE FROM waitlist WHERE user_id = ?", (uid,))
        db.audit(ctx.conn, uid, "account_deleted", ctx.user["username"])
    avatar_file(uid).unlink(missing_ok=True)
    ctx.cookies[config.SESSION_COOKIE] = (None, 0)
    raise Redirect("/")
