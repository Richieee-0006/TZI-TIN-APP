"""Přihlášení, registrace, trial režim a odhlášení."""
from html import escape
from typing import Optional
from fastapi import APIRouter, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import db
from ..config import HASHED_PASSWORD, SESSION_COOKIE, SESSION_MAX_AGE
from ..pages import LOGIN_REGISTER_HTML
from ..sessions import create_session_token

router = APIRouter()


# --- Authentication & Registration Endpoints ---
@router.get("/login", response_class=HTMLResponse)
def get_login(error: Optional[str] = None, success: Optional[str] = None):
    msg = ""
    if error:
        msg = f'<div class="error-msg">{escape(error)}</div>'
    elif success:
        msg = f'<div class="success-msg">{escape(success)}</div>'

    html = LOGIN_REGISTER_HTML.replace("<!--MESSAGE-->", msg)
    html = html.replace("<!--LOGIN_ACTIVE-->", "active")
    html = html.replace("<!--REG_ACTIVE-->", "")
    html = html.replace("<!--LOGIN_DISPLAY-->", "block")
    html = html.replace("<!--REG_DISPLAY-->", "none")
    return html


@router.post("/login")
def post_login(response: Response, username: str = Form(...), password: str = Form(...)):
    u = username.strip()
    p = password.strip()

    # 1. Admin login check via HASHED_PASSWORD
    if u.lower() == "admin" and HASHED_PASSWORD:
        if db.check_password(p, HASHED_PASSWORD):
            admin_user = {"id": 1, "username": "Admin", "role": "admin", "theme": "games"}
            token = create_session_token(admin_user)
            resp = RedirectResponse(url="/", status_code=303)
            resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
            return resp

    # 2. Student login check via database
    user = db.authenticate_user(u, p)
    if user:
        token = create_session_token(user)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
        return resp

    return RedirectResponse(url="/login?error=Špatné+přihlašovací+jméno+nebo+heslo", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def get_register(error: Optional[str] = None):
    msg = f'<div class="error-msg">{escape(error)}</div>' if error else ""
    html = LOGIN_REGISTER_HTML.replace("<!--MESSAGE-->", msg)
    html = html.replace("<!--LOGIN_ACTIVE-->", "")
    html = html.replace("<!--REG_ACTIVE-->", "active")
    html = html.replace("<!--LOGIN_DISPLAY-->", "none")
    html = html.replace("<!--REG_DISPLAY-->", "block")
    return html


@router.post("/register")
def post_register(
    response: Response,
    username: Optional[str] = Form(None),
    password: str = Form(...),
    password_confirm: Optional[str] = Form(None),
    invite_code: Optional[str] = Form(None),
    theme: str = Form("games")
):
    inv = invite_code.strip() if invite_code else None
    pwd = password.strip()
    uname = username.strip() if username else None

    if len(pwd) < 4:
        return RedirectResponse(url="/register?error=Heslo+musí+mít+alespoň+4+znaky", status_code=303)

    if password_confirm is not None and password_confirm.strip() != pwd:
        return RedirectResponse(url="/register?error=Zadaná+hesla+se+neshodují", status_code=303)

    if uname is not None and len(uname) < 2:
        return RedirectResponse(url="/register?error=Uživatelské+jméno+musí+mít+alespoň+2+znaky", status_code=303)

    ok, err, user = db.register_user(theme=theme, password=pwd, invite_code=inv, username=uname)
    if not ok or not user:
        err_msg = err or "Registrace se nezdařila."
        return RedirectResponse(url=f"/register?error={err_msg}", status_code=303)

    # Automatické přihlášení
    token = create_session_token(user)
    assigned_nick = user["username"]
    resp = RedirectResponse(url=f"/?welcome_nick={assigned_nick}", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.get("/trial")
def get_trial(response: Response):
    trial_user = {
        "id": 0,
        "username": "Host (Trial)",
        "role": "trial",
        "theme": "catppuccin"
    }
    token = create_session_token(trial_user)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, max_age=86400, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
def get_logout(response: Response):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp
