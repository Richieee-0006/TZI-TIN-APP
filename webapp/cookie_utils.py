"""Bezpečné nastavení cookie — podmíněný secure flag dle HTTP/HTTPS a detekce IP za CF Tunnelem."""
from fastapi import Request
from fastapi.responses import Response
from typing import Any, Optional

from .config import SESSION_COOKIE

DEFAULT_SECURE = True  # default pro produkci (HTTPS)


def is_https(request: Optional[Request]) -> bool:
    """Zjistí, zda je spojení HTTPS.
    Kontroluje X-Forwarded-Proto header (proxy) a scheme z requestu.
    """
    if not request:
        return False
    forwarded = request.headers.get("x-forwarded-proto", "").lower()
    if forwarded:
        return forwarded == "https"
    return request.url.scheme == "https"


def get_client_ip(request: Optional[Request]) -> str:
    """Vrátí IP klienta. Za lokálním Cloudflare Tunnelem (loopback + CF-Ray) čte CF-Connecting-IP."""
    if not request:
        return "unknown"
    host = request.client.host if request.client else "unknown"
    if host in ("127.0.0.1", "::1") and request.headers.get("cf-ray"):
        cf_ip = request.headers.get("cf-connecting-ip", "").strip()
        if cf_ip:
            return cf_ip
    return host


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
