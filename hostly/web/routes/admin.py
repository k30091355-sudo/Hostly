"""Admin-Bereich: Übersicht, Codes, User, Tunnel, Server, Einstellungen."""
import ipaddress
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from ... import codes, coins, config, db, security, servers
from ...timeutil import fmt, now_sql
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


# ---------- Übersicht ----------

def _count(conn, sql, *args) -> int:
    return conn.execute(sql, args).fetchone()[0]


@router.get("/admin", response_class=HTMLResponse)
def admin_home(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    c = ctx.conn
    cap = servers.capacity(c)
    by_state = {r["state"]: r["n"] for r in c.execute("SELECT state, COUNT(*) AS n FROM servers GROUP BY state")}
    runtime = c.execute(
        """SELECT SUM(st.running AND NOT st.paused) AS online, SUM(st.running AND st.paused) AS sleeping
           FROM server_status st JOIN servers s ON s.id = st.server_id WHERE s.state = 'active'"""
    ).fetchone()
    stats = {
        "users": _count(c, "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL"),
        "new_users": _count(c, "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND created_at > datetime('now', '-7 days')"),
        "coins_total": _count(c, "SELECT COALESCE(SUM(amount), 0) FROM coin_ledger"),
        "coins_redeemed": _count(c, "SELECT COALESCE(SUM(amount), 0) FROM coin_ledger WHERE reason = 'code'"),
        "coins_spent": -_count(c, "SELECT COALESCE(SUM(amount), 0) FROM coin_ledger WHERE amount < 0"),
        "coins_refunded": _count(c, "SELECT COALESCE(SUM(amount), 0) FROM coin_ledger WHERE reason = 'erstattung'"),
        "codes_active": _count(c, "SELECT COUNT(*) FROM codes WHERE active = 1 AND uses < max_uses AND (expires_at IS NULL OR expires_at > datetime('now'))"),
        "active": by_state.get("active", 0) + by_state.get("creating", 0) + by_state.get("reactivating", 0),
        "archived": by_state.get("archived", 0),
        "online": runtime["online"] or 0,
        "sleeping": runtime["sleeping"] or 0,
        "job_errors": _count(c, "SELECT COUNT(*) FROM jobs WHERE status = 'error' AND created_at > datetime('now', '-1 day')"),
    }
    events = c.execute(
        """SELECT a.action, a.details, a.created_at, u.username FROM audit_log a
           LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT 20"""
    ).fetchall()
    errors = c.execute(
        """SELECT j.*, s.name AS server_name FROM jobs j LEFT JOIN servers s ON s.id = j.server_id
           WHERE j.status = 'error' ORDER BY j.id DESC LIMIT 10"""
    ).fetchall()
    sizes = {k: int(db.get_setting(c, k, "0")) for k in ("size_backups", "size_archives")}
    stats["giveaways"] = _count(c, "SELECT COUNT(*) FROM giveaways WHERE drawn_at IS NULL")
    stats["promos"] = _count(c, "SELECT COUNT(*) FROM promotions WHERE starts_at <= datetime('now') AND ends_at > datetime('now')")
    stats["night"] = _count(c, "SELECT COUNT(*) FROM night_pause_log WHERE status = 'laeuft'")
    from ... import stats as st
    from ...worker import host
    since7 = fmt(datetime.now(timezone.utc) - timedelta(days=7))
    hs = c.execute("SELECT * FROM host_samples WHERE at >= ? ORDER BY at", (since7,)).fetchall()
    last = hs[-1] if hs else None
    charts = None
    if hs:
        mem_total = max((h["mem_total_mb"] or 0) for h in hs) or 1
        disk_total = max((h["disk_total_gb"] or 0) for h in hs) or 1
        charts = {
            "cpu": st.line_chart(hs, "cpu_percent", 100, "CPU", hours=24 * 7),
            "mem": st.line_chart(hs, "mem_used_mb", mem_total, "RAM", hours=24 * 7),
            "disk": st.line_chart(hs, "disk_used_gb", disk_total, "Festplatte", hours=24 * 7),
            "temp": st.line_chart(hs, "temp_c", 100, "Temperatur", hours=24 * 7)
            if any(h["temp_c"] is not None for h in hs) else None,
        }
    return ctx.render("admin/index.html", stats=stats, cap=cap, events=events, errors=errors, sys=system_info(),
                      sizes=sizes, charts=charts, last=last, warnings=host.current_warnings(c))


# ---------- Codes ----------

def _parse_local_date(value: str) -> str | None:
    """Datum aus dem Formular (deutsche Zeit, Ende des Tages) → UTC für die Datenbank."""
    if not value:
        return None
    day = datetime.strptime(value, "%Y-%m-%d").replace(hour=23, minute=59, second=59,
                                                       tzinfo=ZoneInfo(config.TIMEZONE))
    return fmt(day)


@router.get("/admin/codes", response_class=HTMLResponse)
def codes_page(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    rows = ctx.conn.execute("SELECT * FROM codes ORDER BY id DESC LIMIT 500").fetchall()
    new_ids = [int(x) for x in ctx.request.query_params.get("neu", "").split(",") if x.isdigit()]
    new_codes = [r for r in rows if r["id"] in new_ids]
    # Adresse für die Code-Bilder: die öffentliche Tailscale-Adresse, sonst die aktuelle
    site = (db.get_setting(ctx.conn, "public_url") or "").split("://")[-1] or ctx.request.headers.get("host", "")
    return ctx.render("admin/codes.html", rows=rows, status=codes.status, new_codes=new_codes, site=site)


@router.post("/admin/codes")
def create_codes(coins_amount: int = Form(..., alias="coins"), max_uses: int = Form(1), count: int = Form(1),
                 expires: str = Form(""), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    error = None
    if not (config.CODE_MIN_COINS <= coins_amount <= config.CODE_MAX_COINS):
        error = "Coins müssen zwischen 50 und 1000 liegen."
    elif not (1 <= max_uses <= 100000):
        error = "„Wie oft gültig“ muss mindestens 1 sein."
    elif not (1 <= count <= 100):
        error = "Höchstens 100 Codes auf einmal."
    try:
        expires_at = _parse_local_date(expires)
    except ValueError:
        error = "Ungültiges Datum."
    if error:
        rows = ctx.conn.execute("SELECT * FROM codes ORDER BY id DESC LIMIT 500").fetchall()
        return ctx.render("admin/codes.html", status_code=400, rows=rows, status=codes.status,
                          new_codes=[], error=ctx.t(error))
    ids = []
    with db.transaction(ctx.conn):
        for _ in range(count):
            while True:
                try:
                    cur = ctx.conn.execute(
                        "INSERT INTO codes (code, coins, max_uses, expires_at, created_by) VALUES (?, ?, ?, ?, ?)",
                        (codes.generate(), coins_amount, max_uses, expires_at, ctx.user["id"]),
                    )
                    ids.append(cur.lastrowid)
                    break
                except sqlite3.IntegrityError:
                    continue  # extrem selten: gleicher Code schon vorhanden
        db.audit(ctx.conn, ctx.user["id"], "codes_created", f"{count}× {coins_amount} Coins")
    raise Redirect("/admin/codes?neu=" + ",".join(map(str, ids)))


@router.post("/admin/codes/{code_id}")
def edit_code(code_id: int, action: str = Form(...), max_uses: int = Form(0), csrf: str = Form(""),
              ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    if action == "toggle":
        ctx.conn.execute("UPDATE codes SET active = 1 - active WHERE id = ?", (code_id,))
    elif action == "max_uses" and max_uses >= 1:
        ctx.conn.execute("UPDATE codes SET max_uses = ? WHERE id = ?", (max_uses, code_id))
    raise Redirect("/admin/codes")


# ---------- User ----------

@router.get("/admin/user", response_class=HTMLResponse)
def users_page(q: str = "", ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    rows = ctx.conn.execute(
        """SELECT u.id, u.username, u.is_admin, u.created_at,
                  (SELECT COALESCE(SUM(amount), 0) FROM coin_ledger l WHERE l.user_id = u.id) AS balance,
                  (SELECT COUNT(*) FROM servers s WHERE s.owner_id = u.id AND s.state != 'deleted') AS server_count
           FROM users u WHERE u.deleted_at IS NULL AND u.username LIKE ? ORDER BY u.id DESC LIMIT 300""",
        (f"%{q.strip()}%",),
    ).fetchall()
    return ctx.render("admin/users.html", rows=rows, q=q)


def _user_page(ctx: Ctx, user_id: int, status_code: int = 200, **values):
    u = ctx.conn.execute("SELECT * FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,)).fetchone()
    if u is None:
        raise Redirect("/admin/user")
    ledger = ctx.conn.execute(
        "SELECT * FROM coin_ledger WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user_id,)).fetchall()
    user_servers = ctx.conn.execute(
        """SELECT s.*, m.name AS model_name FROM servers s JOIN models m ON m.id = s.model_id
           WHERE s.owner_id = ? AND s.state != 'deleted' ORDER BY s.id DESC""", (user_id,)).fetchall()
    return ctx.render("admin/user.html", status_code=status_code, u=u, ledger=ledger, balance=coins.balance(ctx.conn, user_id),
                      user_servers=user_servers, reasons=coins.REASONS, **values)


@router.get("/admin/user/{user_id}", response_class=HTMLResponse)
def user_page(user_id: int, ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    return _user_page(ctx, user_id)


@router.post("/admin/user/{user_id}/passwort")
def reset_password(user_id: int, csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    """Zufälliges Passwort erzeugen. Der Admin sieht es genau einmal und schickt es dem User."""
    ctx.require_admin()
    ctx.check_csrf(csrf)
    password = security.random_password()
    with db.transaction(ctx.conn):
        ctx.conn.execute("UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?",
                         (security.hash_password(password), user_id))
        ctx.conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        db.audit(ctx.conn, user_id, "password_reset", f"durch {ctx.user['username']}")
    return _user_page(ctx, user_id, new_password=password)


@router.post("/admin/user/{user_id}/coins")
def adjust_coins(user_id: int, amount: int = Form(...), note: str = Form(""), csrf: str = Form(""),
                 ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    if amount == 0 or abs(amount) > 1_000_000:
        return _user_page(ctx, user_id, 400, error=ctx.t("Ungültiger Betrag."))
    try:
        with db.transaction(ctx.conn):
            coins.book(ctx.conn, user_id, amount, "admin", note=note.strip()[:100], created_by=ctx.user["id"])
            db.audit(ctx.conn, user_id, "admin_coins", f"{amount:+d} durch {ctx.user['username']}")
    except coins.NotEnoughCoins:
        return _user_page(ctx, user_id, 400, error=ctx.t("Der Kontostand darf nicht negativ werden."))
    return _user_page(ctx, user_id, success=ctx.t("Gebucht."))


# ---------- Tunnel ----------

def _next_free_ip(conn) -> str:
    used = {r[0] for r in conn.execute("SELECT internal_ip FROM tunnels")}
    for n in range(config.MC_FIRST_SLOT, 250):
        ip = f"{config.MC_NETWORK_PREFIX}{n}"
        if ip not in used:
            return ip
    return ""


def _tunnels_page(ctx: Ctx, status_code: int = 200, **values):
    rows = ctx.conn.execute(
        """SELECT t.*, s.id AS server_id, s.name AS server_name FROM tunnels t
           LEFT JOIN servers s ON s.tunnel_id = t.id ORDER BY t.id"""
    ).fetchall()
    return ctx.render("admin/tunnels.html", status_code=status_code, rows=rows,
                      suggested_ip=_next_free_ip(ctx.conn), **values)


@router.get("/admin/tunnel", response_class=HTMLResponse)
def tunnels_page(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    return _tunnels_page(ctx)


def _valid_slot(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr in ipaddress.ip_network(config.MC_NETWORK_PREFIX + "0/24") and int(str(addr).rsplit(".", 1)[1]) >= config.MC_FIRST_SLOT


@router.post("/admin/tunnel")
def add_tunnel(name: str = Form(...), playit_account: int = Form(1), public_address: str = Form(...),
               internal_ip: str = Form(...), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    name, public_address, internal_ip = name.strip(), public_address.strip(), internal_ip.strip()
    if not name or not public_address or len(name) > 40 or len(public_address) > 120:
        return _tunnels_page(ctx, 400, error=ctx.t("Bitte Name und öffentliche Adresse angeben."))
    if not _valid_slot(internal_ip):
        return _tunnels_page(ctx, 400, error=ctx.t("Der interne Platz muss zwischen 172.30.0.11 und 172.30.0.249 liegen."))
    try:
        ctx.conn.execute(
            "INSERT INTO tunnels (name, playit_account, public_address, internal_ip) VALUES (?, ?, ?, ?)",
            (name, 2 if playit_account == 2 else 1, public_address, internal_ip),
        )
    except sqlite3.IntegrityError:
        return _tunnels_page(ctx, 400, error=ctx.t("Dieser interne Platz ist schon vergeben."))
    raise Redirect("/admin/tunnel")


@router.post("/admin/tunnel/{tunnel_id}")
def edit_tunnel(tunnel_id: int, action: str = Form(...), public_address: str = Form(""), name: str = Form(""),
                csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    in_use = ctx.conn.execute("SELECT 1 FROM servers WHERE tunnel_id = ?", (tunnel_id,)).fetchone()
    if action == "toggle":
        ctx.conn.execute("UPDATE tunnels SET active = 1 - active WHERE id = ?", (tunnel_id,))
    elif action == "save" and public_address.strip() and name.strip():
        ctx.conn.execute("UPDATE tunnels SET public_address = ?, name = ? WHERE id = ?",
                         (public_address.strip()[:120], name.strip()[:40], tunnel_id))
    elif action == "delete":
        if in_use:
            return _tunnels_page(ctx, 400, error=ctx.t("Der Tunnel wird gerade von einem Server benutzt."))
        ctx.conn.execute("DELETE FROM tunnels WHERE id = ?", (tunnel_id,))
    raise Redirect("/admin/tunnel")


# ---------- Server ----------

@router.get("/admin/server", response_class=HTMLResponse)
def servers_page(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    rows = ctx.conn.execute(
        """SELECT s.*, m.name AS model_name, u.username, t.public_address,
                  st.running, st.paused, st.health, st.players_online, st.players_max
           FROM servers s JOIN models m ON m.id = s.model_id JOIN users u ON u.id = s.owner_id
           LEFT JOIN tunnels t ON t.id = s.tunnel_id LEFT JOIN server_status st ON st.server_id = s.id
           WHERE s.state != 'deleted' ORDER BY s.id DESC"""
    ).fetchall()
    return ctx.render("admin/servers.html", rows=rows, display_status=servers.display_status,
                      refund_amount=servers.refund_amount)


@router.post("/admin/server/{server_id}/loeschen")
def admin_delete(server_id: int, refund: str = Form("ja"), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    with db.transaction(ctx.conn):
        server = ctx.conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
        if server and server["state"] != "deleted":
            servers.delete(ctx.conn, server, ctx.user["id"], with_refund=(refund == "ja"))
    raise Redirect("/admin/server")


# ---------- Einstellungen ----------

@router.get("/admin/einstellungen", response_class=HTMLResponse)
def settings_page(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    total, reserve = servers.ram_settings(ctx.conn)
    return ctx.render("admin/settings.html", total=total, reserve=reserve,
                      saved=ctx.request.query_params.get("ok") == "1",
                      maintenance=db.get_setting(ctx.conn, "maintenance_mode") == "1",
                      welcome_coins=db.get_setting(ctx.conn, "welcome_coins") or "0",
                      planned_start=db.get_setting(ctx.conn, "maintenance_planned_start"),
                      planned_end=db.get_setting(ctx.conn, "maintenance_planned_end"))


@router.post("/admin/startcoins")
def save_welcome_coins(welcome_coins: int = Form(0), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    db.set_setting(ctx.conn, "welcome_coins", str(max(0, min(1000, welcome_coins))))
    db.audit(ctx.conn, ctx.user["id"], "welcome_coins", str(welcome_coins))
    raise Redirect("/admin/einstellungen?ok=1")


@router.post("/admin/wartung-planen")
def plan_maintenance(start: str = Form(""), end: str = Form(""), action: str = Form("plan"), csrf: str = Form(""),
                     ctx: Ctx = Depends(get_ctx)):
    """Wartung ankündigen (Countdown-Banner für alle); der worker schaltet sie zur Zeit an und wieder aus."""
    from .events import _local_dt_to_utc
    ctx.require_admin()
    ctx.check_csrf(csrf)
    if action == "cancel":
        db.set_setting(ctx.conn, "maintenance_planned_start", "")
        db.set_setting(ctx.conn, "maintenance_planned_end", "")
    else:
        try:
            s = _local_dt_to_utc(start)
            e = _local_dt_to_utc(end) if end else ""
        except ValueError:
            raise Redirect("/admin/einstellungen")
        if s > now_sql() and (not e or e > s):
            db.set_setting(ctx.conn, "maintenance_planned_start", s)
            db.set_setting(ctx.conn, "maintenance_planned_end", e)
            db.audit(ctx.conn, ctx.user["id"], "maintenance_planned", f"{s} – {e or 'offen'}")
    raise Redirect("/admin/einstellungen?ok=1")


@router.post("/admin/einstellungen")
def save_settings(ram_total_gb: float = Form(...), ram_reserve_gb: float = Form(...), csrf: str = Form(""),
                  ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    if 1 <= ram_total_gb <= 512 and 0 <= ram_reserve_gb < ram_total_gb:
        db.set_setting(ctx.conn, "ram_total_gb", str(ram_total_gb))
        db.set_setting(ctx.conn, "ram_reserve_gb", str(ram_reserve_gb))
    raise Redirect("/admin/einstellungen?ok=1")


# ---------- Backups & Archive (Stufe 7) ----------

@router.get("/admin/backups", response_class=HTMLResponse)
def backups_page(ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    backups = ctx.conn.execute(
        """SELECT b.*, s.name AS server_name FROM backups b JOIN servers s ON s.id = b.server_id
           ORDER BY b.id DESC LIMIT 300""").fetchall()
    archives = ctx.conn.execute(
        """SELECT s.*, u.username FROM servers s JOIN users u ON u.id = s.owner_id
           WHERE s.state = 'archived' ORDER BY s.archived_at""").fetchall()
    sizes = {k: int(db.get_setting(ctx.conn, k, "0")) for k in ("size_backups", "size_archives", "size_servers")}
    return ctx.render("admin/backups.html", backups=backups, archives=archives, sizes=sizes,
                      checked=db.get_setting(ctx.conn, "size_checked_at"))


@router.post("/admin/backups/{backup_id}")
def backup_action(backup_id: int, action: str = Form(...), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    b = ctx.conn.execute("SELECT * FROM backups WHERE id = ?", (backup_id,)).fetchone()
    if b and action == "restore":
        db.add_job(ctx.conn, "restore", b["server_id"], ctx.user["id"], {"backup_id": backup_id})
    elif b and action == "pin":
        ctx.conn.execute("UPDATE backups SET pinned = 1 - pinned WHERE id = ?", (backup_id,))
    elif b and action == "delete":
        db.add_job(ctx.conn, "backup_delete", b["server_id"], ctx.user["id"], {"backup_id": backup_id})
    raise Redirect("/admin/backups")


@router.post("/admin/archiv/{server_id}/loeschen")
def archive_delete(server_id: int, csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    with db.transaction(ctx.conn):
        server = ctx.conn.execute("SELECT * FROM servers WHERE id = ? AND state = 'archived'", (server_id,)).fetchone()
        if server:
            servers.delete(ctx.conn, server, ctx.user["id"], with_refund=False)
    raise Redirect("/admin/backups")


@router.post("/admin/wartung")
def maintenance(enabled: str = Form("0"), csrf: str = Form(""), ctx: Ctx = Depends(get_ctx)):
    ctx.require_admin()
    ctx.check_csrf(csrf)
    db.set_setting(ctx.conn, "maintenance_mode", "1" if enabled == "1" else "0")
    # Von Hand geschaltet → ein altes automatisches Ende (geplante Wartung) gilt nicht mehr,
    # sonst würde der worker eine neue Wartung gleich wieder ausschalten
    db.set_setting(ctx.conn, "maintenance_auto_end", "")
    db.audit(ctx.conn, ctx.user["id"], "maintenance", "an" if enabled == "1" else "aus")
    raise Redirect("/admin/einstellungen?ok=1")


def system_info() -> dict:
    """CPU-Last, RAM, Festplatte – direkt aus Linux gelesen (billig, kein Weckruf)."""
    import os
    import shutil

    info = {"cpu": None, "mem_total": None, "mem_free": None, "disk_total": None, "disk_free": None}
    try:
        load1 = os.getloadavg()[0]
        info["cpu"] = min(100, round(load1 / (os.cpu_count() or 1) * 100))
    except OSError:
        pass
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0]) * 1024
        info["mem_total"], info["mem_free"] = mem.get("MemTotal"), mem.get("MemAvailable")
    except OSError:
        pass
    try:
        du = shutil.disk_usage(config.DATA_DIR if config.DATA_DIR.exists() else "/")
        info["disk_total"], info["disk_free"] = du.total, du.free
    except OSError:
        pass
    return info
