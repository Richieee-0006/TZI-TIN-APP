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

for _router in (auth.router, admin.router, study.router, account.router, competitive.router, pwa.router):
    app.include_router(_router)
