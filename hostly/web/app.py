"""Die Hostly-Website (hostly-web). Start: uvicorn hostly.web.app:app"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import config, db, security
from ..i18n import translate
from .deps import CsrfError, Redirect, cookie_secure, templates
from .routes import account, admin, auth, coins, myservers, pages, shop


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    conn = db.connect()
    try:
        security.cleanup_sessions(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Hostly", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(admin.router)
app.include_router(coins.router)
app.include_router(shop.router)
app.include_router(myservers.router)


@app.middleware("http")
async def add_headers_and_csrf_cookie(request: Request, call_next):
    response = await call_next(request)
    ctx = getattr(request.state, "ctx", None)
    secure = cookie_secure(request)
    if ctx is not None and ctx.new_csrf:
        response.set_cookie(
            config.CSRF_COOKIE, ctx.csrf, max_age=60 * 60 * 24 * 365,
            httponly=True, samesite="lax", secure=secure,
        )
    if ctx is not None:
        for name, (value, max_age) in ctx.cookies.items():
            if value is None:
                response.delete_cookie(name)
            else:
                response.set_cookie(name, value, max_age=max_age, httponly=True, samesite="lax", secure=secure)
    # Sicherheits-Kopfzeilen
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


@app.exception_handler(Redirect)
async def handle_redirect(request: Request, exc: Redirect):
    return RedirectResponse(exc.url, status_code=303)


def _lang(request: Request) -> str:
    ctx = getattr(request.state, "ctx", None)
    return ctx.lang if ctx else request.cookies.get("hostly_lang", config.DEFAULT_LANGUAGE)


@app.exception_handler(CsrfError)
async def handle_csrf(request: Request, exc: CsrfError):
    lang = _lang(request)
    return _simple_page(request, lang, 400, translate(lang, "err.csrf"))


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    lang = _lang(request)
    key = "err.not_found" if exc.status_code == 404 else "err.generic"
    return _simple_page(request, lang, exc.status_code, translate(lang, key))


def _simple_page(request: Request, lang: str, status: int, message: str) -> HTMLResponse:
    def t(key, **v):
        return translate(lang, key, **v)

    theme = request.cookies.get("hostly_theme", "system")
    return templates.TemplateResponse(
        request, "error.html",
        {"ctx": None, "t": t, "user": None, "csrf": "", "message": message, "lang": lang, "theme": theme},
        status_code=status,
    )
