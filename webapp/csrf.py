"""CSRF ochrana — generování a validace tokenů ve skrytém cookie."""
import secrets
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import Response
from .config import SESSION_COOKIE

CSRF_COOKIE_NAME = "csrf_token"


def generate_csrf_token(resp: Response) -> str:
    """Vygeneruje nový CSRF token a uloží ho do cookie."""
    token = secrets.token_hex(32)
    resp.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=False,  # nastaveno později middlewarem / helperem
    )
    return token


def get_csrf_token(resp: Response) -> str:
    """Vrátí existující token z cookie nebo vygeneruje nový."""
    existing = resp.cookies.get(CSRF_COOKIE_NAME)
    if existing:
        return existing
    return generate_csrf_token(resp)


def validate_csrf(request: Request, resp: Response) -> bool:
    """Ověří CSRF token z cookie shodou s hodnotou z těla nebo hlavičky.
    Vrací True pokud je token validní, jinak vyvolá HTTPException 403.
    """
    cookie_token: Optional[str] = request.cookies.get(CSRF_COOKIE_NAME)
    # Zkusme z POST těla (defaultní form-urlencoded)
    form_token: Optional[str] = request.form.get("csrf_token")
    # Zkusme z hlavičky (pro AJAX/fetch)
    header_token: Optional[str] = request.headers.get("x-csrf-token")

    token = form_token or header_token
    if not token or not cookie_token:
        raise HTTPException(status_code=403, detail="Chybějící CSRF token.")
    if not secrets.compare_digest(token, cookie_token):
        raise HTTPException(status_code=403, detail="Neplatný CSRF token.")

    # Rotace tokenu po každém úspěšném requestu
    generate_csrf_token(resp)
    return True


def clear_csrf_cookie(resp: Response) -> None:
    """Smazá CSRF cookie (např. po odhlášení)."""
    resp.delete_cookie(CSRF_COOKIE_NAME, path="/")
