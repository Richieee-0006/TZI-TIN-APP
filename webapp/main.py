"""Skládá FastAPI aplikaci: inicializace DB, cache otázek, auto-sync bank a připojení routerů."""
import logging
import threading
import time

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import db
import tzi_trener
from . import questions, uni_bridge
from .config import HASHED_PASSWORD
from .cookie_utils import get_client_ip, is_https
from .git_sync import sync_worker
from .sessions import get_current_user
from .routers import account, admin, auth, competitive, pwa, study

_log = logging.getLogger(__name__)

# --- Initialize Database ---
db.init_db()
if HASHED_PASSWORD:
    db.ensure_admin_exists(HASHED_PASSWORD)

# Cache otázek pro anti-spoofing ověřování odpovědí
questions.refresh_questions()

# Pravidelný auto-sync bank otázek z upstreamu
threading.Thread(target=sync_worker, daemon=True).start()

# --- FastAPI Application ---
app = FastAPI(title="TZI Trenér", docs_url=None, redoc_url=None)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path == "/":
        script_src = "script-src 'self' 'wasm-unsafe-eval'"
        tt_policy = "trusted-types tzi-sw"
    else:
        script_src = "script-src 'self'"
        tt_policy = "trusted-types 'none'"
    csp = (
        "default-src 'none'; "
        f"{script_src}; "
        "style-src 'self' https://fonts.googleapis.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "manifest-src 'self'; "
        "worker-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "require-trusted-types-for 'script'; "
        f"{tt_policy}"
    )
    if is_https(request):
        csp += "; upgrade-insecure-requests"
    response.headers["Content-Security-Policy"] = csp
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if "text/html" in response.headers.get("content-type", "") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    if (
        uni_bridge.is_migration_mode()
        and response.status_code == 200
        and "text/html" in response.headers.get("content-type", "")
    ):
        chunks = [chunk async for chunk in response.body_iterator]
        raw_body = b"".join(chunks)
        html_text = raw_body.decode("utf-8", errors="replace")
        patched = uni_bridge.inject_deprecation_banner(html_text).encode("utf-8")
        new_resp = Response(
            content=patched,
            status_code=response.status_code,
            media_type=response.media_type,
        )
        for k, v in response.headers.items():
            if k.lower() != "content-length":
                new_resp.headers.append(k, v)
        new_resp.headers["content-length"] = str(len(patched))
        return new_resp
    return response


@app.middleware("http")
async def audit_communication_middleware(request: Request, call_next):
    path = request.url.path
    # Přeskočit statické soubory a PWA ikony, ať nezahlcují DB
    if path.startswith("/static") or path in ("/sw.js", "/manifest.webmanifest", "/icon.svg", "/favicon.ico"):
        return await call_next(request)

    # Přeskočit i samotné logování chyb aby nedošlo k rekurzi
    if path == "/api/client-error":
        return await call_next(request)

    t0 = time.time()
    user_id = None
    try:
        u = get_current_user(request)
        if u:
            user_id = u.get("user_id")
    except Exception as exc:
        _log.debug("Audit user lookup skipped: %s", exc)

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = int((time.time() - t0) * 1000)
        ip = get_client_ip(request)
        db.log_error(
            level="ERROR",
            message=f"{request.method} {path} -> 500 Exception: {str(exc)} [{duration_ms}ms, ip={ip}]",
            endpoint=path,
            user_id=user_id,
            stack_trace=str(exc)
        )
        raise exc

    duration_ms = int((time.time() - t0) * 1000)
    status_code = response.status_code
    ip = get_client_ip(request)

    # Logovat WARNING pro 4xx odpovědi (neúspěšné pokusy, rate limity, odmítnutí)
    if 400 <= status_code < 500:
        db.log_error(
            level="WARNING",
            message=f"{request.method} {path} -> {status_code} [{duration_ms}ms, ip={ip}]",
            endpoint=path,
            user_id=user_id
        )
    # Logovat INFO pro API a formulářové komunikace (POST, PUT, DELETE nebo /api/*)
    elif path.startswith("/api/") or request.method in ("POST", "PUT", "DELETE"):
        db.log_error(
            level="INFO",
            message=f"{request.method} {path} -> {status_code} [{duration_ms}ms, ip={ip}]",
            endpoint=path,
            user_id=user_id
        )

    return response

# Statické soubory pro modularizované UI (CSS, JS)
app.mount("/static", StaticFiles(directory=tzi_trener.UI_DIR), name="static")

for _router in (auth.router, admin.router, study.router, account.router, competitive.router, pwa.router):
    app.include_router(_router)
