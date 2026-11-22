"""Admin-Bereich (Stufe 1: Übersicht + Umschalter Admin-/User-Ansicht)."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ..deps import Ctx, Redirect, get_ctx
from .auth import safe_next

router = APIRouter()


@router.post("/admin/ansicht")
def toggle_view(back: str = Form("/"), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    """Admin schaltet zwischen Admin-Ansicht und normaler User-Ansicht um."""
    ctx.require_login()
    ctx.check_csrf(csrf)
    if not ctx.user["is_admin"]:
        raise Redirect("/")
    new_value = 0 if ctx.session["admin_view"] else 1
    ctx.conn.execute("UPDATE sessions SET admin_view = ? WHERE id = ?", (new_value, ctx.session["id"]))
    target = safe_next(back)
    if not new_value and target.startswith("/admin"):
        target = "/"
    raise Redirect(target)


@router.get("/admin", response_class=HTMLResponse)
def admin_home(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    users = ctx.conn.execute(
        "SELECT id, username, is_admin, created_at FROM users WHERE deleted_at IS NULL ORDER BY id DESC LIMIT 200"
    ).fetchall()
    stats = {
        "users": ctx.conn.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL").fetchone()[0],
        "new_users": ctx.conn.execute(
            "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND created_at > datetime('now', '-7 days')"
        ).fetchone()[0],
    }
    events = ctx.conn.execute(
        """SELECT a.action, a.details, a.created_at, u.username FROM audit_log a
           LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT 20"""
    ).fetchall()
    return ctx.render("admin/index.html", users=users, stats=stats, events=events)
