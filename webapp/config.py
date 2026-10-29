"""Konfigurace z prostředí a souboru .env (tajné klíče, cookie, délka session)."""
import os
from pathlib import Path

from itsdangerous import URLSafeTimedSerializer

# Kořen projektu (složka se server.py, db.py, banky/ a ui/)
BASE = Path(__file__).resolve().parent.parent


# --- Environment Configuration ---
def load_env():
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

load_env()

APP_SECRET = os.environ.get("APP_SECRET", "tzi-tin-super-secret-key-39281")
HASHED_PASSWORD = os.environ.get("HASHED_PASSWORD", "").strip()
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").strip()
SESSION_COOKIE = "tzi_session"
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", 86400 * 30))

serializer = URLSafeTimedSerializer(APP_SECRET)
