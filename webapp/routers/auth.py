"""Přihlášení, registrace, trial režim a odhlášení."""
import time
from collections import defaultdict
from html import escape
from typing import Optional, List, Tuple
from fastapi import APIRouter, Response, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import db
from ..config import HASHED_PASSWORD, SESSION_COOKIE, SESSION_MAX_AGE
from ..pages import LOGIN_REGISTER_HTML
from ..sessions import create_session_token
from ..csrf import validate_csrf, clear_csrf_cookie, generate_csrf_token
from ..cookie_utils import set_secure_cookie

router = APIRouter()

# --- Rate limiting: sliding window per IP ---
# (IP -> list of timestamps)
_rate_limit_store: dict[str, List[float]] = defaultdict(list)
RATE_LIMIT_MAX_ATTEMPTS = 10  # max pokusů
RATE_LIMIT_WINDOW = 600      # okno v sekundách (10 minut)


def _check_rate_limit(ip: str) -> bool:
    """Vrací True pokud je IP překročila limit."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    # Odstraníme staré záznamy
    timestamps = _rate_limit_store[ip]
    _rate_limit_store[ip] = [t for t in timestamps if t > window_start]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_MAX_ATTEMPTS:
        return True
    return False


def _record_attempt(ip: str) -> None:
    """Zaznamená pokus do rate limitu."""
    _rate_limit_store[ip].append(time.time())


@router.get("/login", response_class=HTMLResponse)
def get_login(request: Request, error: Optional[str] = None, success: Optional[str] = None):
    msg = ""
    if error:
        msg = f'<div class="error-msg">{escape(error)}</div>'
    elif success:
        msg = f"<div class='success-msg'>{escape(success)}</div>"

    # Generování CSRF tokenu do cookie
    resp = HTMLResponse(content="")
    token = generate_csrf_token(resp)
    csrf_input = f'<input type="hidden" name="csrf_token" value="{escape(token)}">'

    html = LOGIN_REGISTER_HTML
    html = html.replace("<!--MESSAGE-->", msg)
    html = html.replace("<!--LOGIN_ACTIVE-->", "active")
    html = html.replace("<!--REG_ACTIVE-->", "")
    html = html.replace("<!--LOGIN_DISPLAY-->", "block")
    html = html.replace("<!--REG_DISPLAY-->", "none")
    html = html.replace("<!--CSRF-->", csrf_input)

    return HTMLResponse(content=html, headers={"content-type": "text/html; charset=utf-8"})


@router.post("/login")
async def post_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(None),
):
    # CSRF validace
    await validate_csrf(request, response, csrf_token=csrf_token)

    # Rate limiting
    ip = request.client.host if request.client else "unknown"
    if _check_rate_limit(ip):
        return RedirectResponse(url="/login?error=Příliš+mnoho+pokusů.+Počkejte+10+minut", status_code=303)

    u = username.strip()
    p = password.strip()

    # 1. Admin login check via HASHED_PASSWORD
    if u.lower() == "admin" and HASHED_PASSWORD:
        if db.check_password(p, HASHED_PASSWORD):
            admin_user = {"id": 1, "username": "Admin", "role": "admin", "theme": "games"}
            token = create_session_token(admin_user, request)
            resp = RedirectResponse(url="/", status_code=303)
            set_secure_cookie(resp, SESSION_COOKIE, token, request, max_age=SESSION_MAX_AGE)
            return resp

    # 2. Student login check via database
    user = db.authenticate_user(u, p)
    if user:
        token = create_session_token(user, request)
        resp = RedirectResponse(url="/", status_code=303)
        set_secure_cookie(resp, SESSION_COOKIE, token, request, max_age=SESSION_MAX_AGE)
        return resp

    _record_attempt(ip)
    return RedirectResponse(url="/login?error=Špatné+přihlašovací+jméno+nebo+heslo", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def get_register(request: Request, error: Optional[str] = None):
    msg = f'<div class="error-msg">{escape(error)}</div>' if error else ""

    # Generování CSRF tokenu do cookie
    resp = HTMLResponse(content="")
    token = generate_csrf_token(resp)
    csrf_input = f'<input type="hidden" name="csrf_token" value="{escape(token)}">'

    html = LOGIN_REGISTER_HTML
    html = html.replace("<!--MESSAGE-->", msg)
    html = html.replace("<!--LOGIN_ACTIVE-->", "")
    html = html.replace("<!--REG_ACTIVE-->", "active")
    html = html.replace("<!--LOGIN_DISPLAY-->", "none")
    html = html.replace("<!--REG_DISPLAY-->", "block")
    html = html.replace("<!--CSRF-->", csrf_input)

    return HTMLResponse(content=html, headers={"content-type": "text/html; charset=utf-8"})


@router.post("/register")
async def post_register(
    request: Request,
    response: Response,
    username: Optional[str] = Form(None),
    password: str = Form(...),
    password_confirm: Optional[str] = Form(None),
    theme: str = Form("games"),
    csrf_token: Optional[str] = Form(None),
):
    # CSRF validace
    await validate_csrf(request, response, csrf_token=csrf_token)

    # Rate limiting
    ip = request.client.host if request.client else "unknown"
    if _check_rate_limit(ip):
        return RedirectResponse(url="/register?error=Příliš+mnoho+pokusů.+Počkejte+10+minut", status_code=303)

    pwd = password.strip()
    uname = username.strip() if username else None

    if len(pwd) < 8:
        _record_attempt(ip)
        return RedirectResponse(url="/register?error=Heslo+musí+mít+alespoň+8+znaků", status_code=303)

    if password_confirm is not None and password_confirm.strip() != pwd:
        _record_attempt(ip)
        return RedirectResponse(url="/register?error=Zadaná+hesla+se+neshodují", status_code=303)

    if uname is not None and len(uname) < 2:
        _record_attempt(ip)
        return RedirectResponse(url="/register?error=Uživatelské+jméno+musí+mít+alespoň+2+znaky", status_code=303)

    ok, err, user = db.register_user(theme=theme, password=pwd, username=uname)
    if not ok or not user:
        err_msg = err or "Registrace se nezdařila."
        return RedirectResponse(url=f"/register?error={err_msg}", status_code=303)

    # Automatické přihlášení
    token = create_session_token(user, request)
    assigned_nick = user["username"]
    resp = RedirectResponse(url=f"/?welcome_nick={assigned_nick}", status_code=303)
    set_secure_cookie(resp, SESSION_COOKIE, token, request, max_age=SESSION_MAX_AGE)
    return resp


@router.get("/trial")
def get_trial(request: Request, response: Response):
    trial_user = {
        "id": 0,
        "username": "Host (Trial)",
        "role": "trial",
        "theme": "catppuccin"
    }
    token = create_session_token(trial_user, request)
    resp = RedirectResponse(url="/", status_code=303)
    set_secure_cookie(resp, SESSION_COOKIE, token, request, max_age=86400)
    return resp


@router.get("/logout")
def get_logout(request: Request, response: Response):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    clear_csrf_cookie(resp)
    return resp
