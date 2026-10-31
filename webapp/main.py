from fastapi.staticfiles import StaticFiles
import tzi_trener
"""Skládá FastAPI aplikaci: inicializace DB, cache otázek, auto-sync bank a připojení routerů."""
import threading

from fastapi import FastAPI

import db
from . import questions
from .config import HASHED_PASSWORD
from .git_sync import sync_worker
from .routers import account, admin, auth, competitive, pwa, study

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
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'"
    )
    if request.url.scheme == "https":
        csp += "; upgrade-insecure-requests"
    response.headers["Content-Security-Policy"] = csp
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# Statické soubory pro modularizované UI (CSS, JS)
app.mount("/static", StaticFiles(directory=tzi_trener.UI_DIR), name="static")

for _router in (auth.router, admin.router, study.router, account.router, competitive.router, pwa.router):
    app.include_router(_router)
