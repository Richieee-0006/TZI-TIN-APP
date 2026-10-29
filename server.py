"""Vstupní bod TZI Trenéra (FastAPI + SQLite). Spuštění: python server.py (port 5051).

Aplikace je rozdělená do balíčku webapp/ (routery, session, šablony), bodování je v scoring/,
databáze v db.py. Podrobnosti viz ARCHITECTURE.md. Jména níže jsou re-exportovaná kvůli testům a skriptům.
"""
import uvicorn

from webapp.config import SESSION_COOKIE  # noqa: F401
from webapp.git_sync import git_pull  # noqa: F401
from webapp.main import app
from webapp.questions import refresh_questions  # noqa: F401
from webapp.sessions import create_session_token, require_user  # noqa: F401


def main():
    port = 5051
    host = "127.0.0.1"
    print(f"==================================================")
    print(f"  TZI Trenér (FastAPI + SQLite + Multi-User)")
    print(f"  Běží na: http://{host}:{port}")
    print(f"==================================================")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
