"""Gewinnspiele und Rabatt-/RAM-Aktionen (Stufe 6)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ... import config, db, promotions, servers
from ...timeutil import fmt, now_sql
from ..deps import Ctx, Redirect, get_ctx

router = APIRouter()


def active_giveaways(conn, user_id: int | None):
    return conn.execute(
        """SELECT g.*, (SELECT COUNT(*) FROM giveaway_entries e WHERE e.giveaway_id = g.id) AS entries,
                  EXISTS (SELECT 1 FROM giveaway_entries e WHERE e.giveaway_id = g.id AND e.user_id = ?) AS joined
           FROM giveaways g WHERE g.drawn_at IS NULL AND g.ends_at > ? ORDER BY g.ends_at""",
        (user_id, now_sql()),
    ).fetchall()


def promo_label(conn, p) -> str:
    names = {m["id"]: m["name"] for m in servers.models(conn)}
    target = "alle Server" if p["model_ids"] == "all" else \
        ", ".join(names.get(int(i), "?") for i in p["model_ids"].split(",") if i)
    if p["kind"] == "rabatt":
        return f"−{p['percent']} % auf {target}"
    return f"+{p['extra_ram_gb']:g} GB RAM für {target} (bei neuen Mieten)"


# ---------- öffentlich ----------

@router.get("/gewinnspiele", response_class=HTMLResponse)
def giveaways_page(ctx: Ctx = Depends(get_ctx)):
    uid = ctx.user["id"] if ctx.user else None
    past = ctx.conn.execute("SELECT * FROM giveaways WHERE drawn_at IS NOT NULL ORDER BY drawn_at DESC LIMIT 10").fetchall()
    winners = {g["id"]: [r[0] for r in ctx.conn.execute(
        """SELECT u.username FROM giveaway_entries e JOIN users u ON u.id = e.user_id
           WHERE e.giveaway_id = ? AND e.is_winner = 1""", (g["id"],))] for g in past}
    return ctx.render("giveaways.html", active=active_giveaways(ctx.conn, uid), past=past, winners=winners)


@router.post("/gewinnspiele/{giveaway_id}/teilnehmen")
def join(giveaway_id: int, csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_login()
    ctx.check_csrf(csrf)
    g = ctx.conn.execute("SELECT * FROM giveaways WHERE id = ? AND drawn_at IS NULL AND ends_at > ?",
                         (giveaway_id, now_sql())).fetchone()
    if g:
        ctx.conn.execute("INSERT OR IGNORE INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
                         (giveaway_id, ctx.user["id"]))
    raise Redirect("/gewinnspiele?ok=1")


# ---------- Admin: Gewinnspiele ----------

@router.get("/admin/gewinnspiele", response_class=HTMLResponse)
def admin_giveaways(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    rows = ctx.conn.execute(
        """SELECT g.*, (SELECT COUNT(*) FROM giveaway_entries e WHERE e.giveaway_id = g.id) AS entries
           FROM giveaways g ORDER BY g.id DESC LIMIT 100""").fetchall()
    return ctx.render("admin/giveaways.html", rows=rows)


@router.post("/admin/gewinnspiele")
def create_giveaway(title: str = Form(...), description: str = Form(""), coins_per_winner: int = Form(...),
                    winner_count: int = Form(1), days: int = Form(7), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    if title.strip() and 1 <= coins_per_winner <= 100000 and 1 <= winner_count <= 1000 and 1 <= days <= 365:
        ctx.conn.execute(
            """INSERT INTO giveaways (title, description, coins_per_winner, winner_count, ends_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title.strip()[:80], description.strip()[:300], coins_per_winner, winner_count,
             fmt(datetime.now(timezone.utc) + timedelta(days=days)), ctx.user["id"]))
    raise Redirect("/admin/gewinnspiele")


@router.post("/admin/gewinnspiele/{giveaway_id}/beenden")
def end_giveaway(giveaway_id: int, csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    """Sofort beenden → der worker lost in der nächsten Minute aus."""
    ctx.require_admin()
    ctx.check_csrf(csrf)
    ctx.conn.execute("UPDATE giveaways SET ends_at = ? WHERE id = ? AND drawn_at IS NULL", (now_sql(), giveaway_id))
    raise Redirect("/admin/gewinnspiele")


# ---------- Admin: Aktionen ----------

def _local_to_utc(value: str, end_of_day: bool) -> str:
    d = datetime.strptime(value, "%Y-%m-%d")
    d = d.replace(hour=23, minute=59, second=59) if end_of_day else d
    return fmt(d.replace(tzinfo=ZoneInfo(config.TIMEZONE)))


@router.get("/admin/aktionen", response_class=HTMLResponse)
def admin_promotions(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    rows = ctx.conn.execute("SELECT * FROM promotions ORDER BY ends_at DESC LIMIT 100").fetchall()
    return ctx.render("admin/promotions.html", rows=rows, models=servers.models(ctx.conn),
                      label=lambda p: promo_label(ctx.conn, p), now=now_sql())


@router.post("/admin/aktionen")
async def create_promotion(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    form = await ctx.request.form()
    ctx.check_csrf(form.get("csrf"))
    kind = form.get("kind")
    model_ids = form.getlist("model_ids")
    try:
        starts = _local_to_utc(form.get("starts", ""), False)
        ends = _local_to_utc(form.get("ends", ""), True)
        percent = int(form.get("percent") or 0)
        extra = float(form.get("extra_ram_gb") or 0)
    except ValueError:
        raise Redirect("/admin/aktionen")
    ids = "all" if not model_ids or len(model_ids) == 3 else ",".join(i for i in model_ids if i.isdigit())
    ok = ends > starts and form.get("title", "").strip() and (
        (kind == "rabatt" and 1 <= percent <= 75) or (kind == "ram" and 0.5 <= extra <= 8))
    if ok:
        ctx.conn.execute(
            "INSERT INTO promotions (kind, title, percent, extra_ram_gb, model_ids, starts_at, ends_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, form["title"].strip()[:80], percent if kind == "rabatt" else 0, extra if kind == "ram" else 0,
             ids, starts, ends))
    raise Redirect("/admin/aktionen")


@router.post("/admin/aktionen/{promo_id}/beenden")
def end_promotion(promo_id: int, csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    p = ctx.conn.execute("SELECT * FROM promotions WHERE id = ? AND ends_at > ?", (promo_id, now_sql())).fetchone()
    if p:
        with db.transaction(ctx.conn):
            ctx.conn.execute("UPDATE promotions SET ends_at = ? WHERE id = ?", (now_sql(), promo_id))
            if p["kind"] == "ram":   # Extra-RAM der Server endet mit der Aktion
                ctx.conn.execute("UPDATE servers SET extra_ram_until = ? WHERE extra_ram_until = ? AND extra_ram_gb > 0",
                                 (now_sql(), p["ends_at"]))
    raise Redirect("/admin/aktionen")


def home_events(ctx: Ctx) -> dict:
    """Für die Startseite: laufende Aktionen und Gewinnspiele."""
    promos = promotions.active(ctx.conn)
    return {"promos": [(p, promo_label(ctx.conn, p)) for p in promos],
            "giveaways": active_giveaways(ctx.conn, ctx.user["id"] if ctx.user else None)}
