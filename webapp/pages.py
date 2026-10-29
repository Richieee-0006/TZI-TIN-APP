"""HTML šablony přihlášení/registrace a admin panelu (soubory v webapp/templates/)."""
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _load(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


LOGIN_REGISTER_HTML = _load("login_register.html")
ADMIN_HTML = _load("admin.html")
