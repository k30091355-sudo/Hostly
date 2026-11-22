"""Gemeinsame Bausteine für alle Seiten: Datenbank, angemeldeter User, Sprache, Design, CSRF."""
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from .. import config, db, security
from ..i18n import translate

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["SUPPORT_EMAIL"] = config.SUPPORT_EMAIL
templates.env.globals["VERSION"] = config.VERSION

_BERLIN = ZoneInfo("Europe/Berlin")


def _localtime(value: str | None) -> str:
    """Zeit aus der Datenbank (UTC) in deutscher Ortszeit anzeigen."""
    if not value:
        return ""
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(_BERLIN).strftime("%d.%m.%Y %H:%M")


templates.env.filters["localtime"] = _localtime


@pass_context
def _remaining(context, until: str | None) -> str:
    """Restlaufzeit als Text, z. B. "12 Tage" / "12 days" (Sprache des Users)."""
    if not until:
        return ""
    ctx = context.get("ctx")
    en = (ctx.lang if ctx else context.get("lang")) == "en"
    seconds = (datetime.strptime(until, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
               - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        return "expired" if en else "abgelaufen"
    days = int(seconds // 86400)
    if days >= 2:
        return f"{days} days" if en else f"{days} Tage"
    if days == 1:
        return "1 day" if en else "1 Tag"
    hours = int(seconds // 3600)
    if hours >= 1:
        return f"{hours} h" if en else f"{hours} Std."
    return f"{int(seconds // 60)} min" if en else f"{int(seconds // 60)} Min."


templates.env.filters["remaining"] = _remaining
templates.env.filters["coins"] = lambda n: f"{int(n):,}".replace(",", ".")
from ..motd import to_html as _motd_html  # noqa: E402
templates.env.filters["motd"] = _motd_html
import json as _json  # noqa: E402
templates.env.filters["fromjson"] = lambda v: _json.loads(v or "{}")


class Redirect(Exception):
    """Wird geworfen, um sofort auf eine andere Seite umzuleiten."""

    def __init__(self, url: str):
        self.url = url


class CsrfError(Exception):
    pass


class MaintenanceError(Exception):
    pass


# Was im Wartungsmodus für normale User noch geht
_MAINTENANCE_ALLOWED = ("/login", "/abmelden", "/design", "/sprache", "/meldung/")
_public_url_seen: set = set()


@dataclass
class Ctx:
    request: Request
    conn: sqlite3.Connection
    user: sqlite3.Row | None
    session: dict | None
    lang: str
    theme: str
    csrf: str
    new_csrf: bool = False
    cookies: dict = field(default_factory=dict)  # Cookies, die gesetzt werden sollen
    cache: dict = field(default_factory=dict)
    maintenance: bool = False
    maintenance_planned: str | None = None

    # --- Hilfen ---
    def t(self, key: str, **values) -> str:
        return translate(self.lang, key, **values)

    @property
    def balance(self) -> int:
        """Coin-Stand des angemeldeten Users (für die Kopfleiste)."""
        if self.user is None:
            return 0
        if "balance" not in self.cache:
            from ..coins import balance
            self.cache["balance"] = balance(self.conn, self.user["id"])
        return self.cache["balance"]

    @property
    def is_admin(self) -> bool:
        """Admin UND gerade in der Admin-Ansicht."""
        return bool(self.user and self.user["is_admin"] and self.session and self.session["admin_view"])

    @property
    def ip(self) -> str | None:
        return self.request.client.host if self.request.client else None

    def require_login(self) -> None:
        if self.user is None:
            path = self.request.url.path
            if self.request.url.query:
                path += "?" + self.request.url.query
            raise Redirect("/login?next=" + quote(path, safe=""))

    def require_admin(self) -> None:
        self.require_login()
        if not self.is_admin:
            raise Redirect("/")

    def check_csrf(self, form_value: str | None) -> None:
        header = self.request.headers.get("x-csrf-token")
        if not security.csrf_ok(self.request.cookies.get(config.CSRF_COOKIE), form_value or header):
            raise CsrfError()

    def can_manage(self, server) -> bool:
        return self.user is not None and (server["owner_id"] == self.user["id"] or self.is_admin)

    def render(self, template: str, status_code: int = 200, **values) -> HTMLResponse:
        values.update(ctx=self, t=self.t, user=self.user, csrf=self.csrf)
        response = templates.TemplateResponse(self.request, template, values, status_code=status_code)
        return response


def cookie_secure(request: Request) -> bool:
    """Cookies nur über HTTPS schicken, wenn die Seite über HTTPS aufgerufen wird
    (Tailscale Funnel). Lokal über http://localhost:8000 klappt der Login trotzdem."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", "")
    return proto == "https" or host.endswith(".ts.net")


# Pfade, die auch erreichbar sind, solange der User sein Passwort ändern muss
_MUST_CHANGE_ALLOWED = ("/einstellungen", "/abmelden", "/static")


def get_ctx(request: Request):
    """FastAPI-Abhängigkeit: baut den Seiten-Kontext und schließt danach die DB."""
    conn = db.connect()
    try:
        token = request.cookies.get(config.SESSION_COOKIE)
        session, user = security.load_session(conn, token)

        if user is not None:
            lang, theme = user["language"], user["theme"]
        else:
            lang = request.cookies.get("hostly_lang", config.DEFAULT_LANGUAGE)
            theme = request.cookies.get("hostly_theme", "system")
        if lang not in config.LANGUAGES:
            lang = config.DEFAULT_LANGUAGE
        if theme not in config.THEMES:
            theme = "system"

        csrf = request.cookies.get(config.CSRF_COOKIE)
        new_csrf = not csrf
        if new_csrf:
            csrf = security.new_csrf_token()

        ctx = Ctx(request, conn, user, session, lang, theme, csrf, new_csrf)

        ctx.maintenance = db.get_setting(conn, "maintenance_mode") == "1"
        planned = db.get_setting(conn, "maintenance_planned_start") or ""
        ctx.maintenance_planned = planned if planned and not ctx.maintenance else None
        if (ctx.maintenance and request.method == "POST" and not (user is not None and user["is_admin"])
                and not request.url.path.startswith(_MAINTENANCE_ALLOWED)):
            raise MaintenanceError()

        # öffentliche Adresse merken (für Resourcepack-Links und /trigger code)
        host = request.headers.get("host", "")
        if host.endswith(".ts.net") and host not in _public_url_seen:
            db.set_setting(conn, "public_url", f"https://{host}")
            _public_url_seen.add(host)

        if user is not None and user["must_change_password"]:
            if not request.url.path.startswith(_MUST_CHANGE_ALLOWED):
                raise Redirect("/einstellungen")

        request.state.ctx = ctx
        yield ctx
    finally:
        conn.close()
