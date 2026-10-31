"""Bezpečné nastavení cookie — podmíněný secure flag dle HTTP/HTTPS."""
from fastapi import Request
from fastapi.responses import Response
from typing import Any, Dict

from .config import SESSION_COOKIE

DEFAULT_SECURE = True  # default pro produkci (HTTPS)


def is_https(request: Request) -> bool:
    """Zjistí, zda je spojení HTTPS.
    Kontroluje X-Forwarded-Proto header (proxy) a scheme z requestu.
    """
    forwarded = request.headers.get("x-forwarded-proto", "").lower()
    if forwarded:
        return forwarded == "https"
    return request.url.scheme == "https"


def set_secure_cookie(
    resp: Response,
    key: str,
    value: str,
    request: Request,
    max_age: int = 86400 * 30,
    httponly: bool = True,
    samesite: str = "lax",
    path: str = "/",
    **kwargs: Any,
) -> None:
    """Nastaví cookie s bezpečným secure flagem.
    Na HTTP localhost je secure=False (aby fungovala), na HTTPS True.
    """
    secure_val = is_https(request) if request else DEFAULT_SECURE
    resp.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=httponly,
        samesite=samesite,
        secure=secure_val,
        path=path,
        **kwargs,
    )
