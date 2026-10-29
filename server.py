import os
import sys
import time
import json
import secrets
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any

import unicodedata
from fastapi import FastAPI, Request, Response, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import db
import scoring
import tzi_trener

BASE = Path(__file__).resolve().parent

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

# --- Initialize Database ---
db.init_db()
if HASHED_PASSWORD:
    db.ensure_admin_exists(HASHED_PASSWORD)


# --- Git Auto-sync Worker (pouze banky otázek z upstreamu) ---
def git_pull():
    try:
        print("[Auto-sync] Kontroluji nové banky otázek z upstream/main...")
        fetch_res = subprocess.run(
            ["git", "fetch", "upstream", "main"],
            cwd=BASE, capture_output=True, text=True, timeout=30
        )
        if fetch_res.returncode != 0:
            err = (fetch_res.stdout + "\n" + fetch_res.stderr).strip()
            print(f"[Auto-sync] Chyba při git fetch upstream: {err}")
            return err

        checkout_res = subprocess.run(
            ["git", "checkout", "upstream/main", "--", "banky"],
            cwd=BASE, capture_output=True, text=True, timeout=30
        )
        out = (checkout_res.stdout + "\n" + checkout_res.stderr).strip()

        # Okamžitě obnovit cache otázek v paměti běžícího serveru
        if "refresh_questions" in globals():
            refresh_questions()

        # Pokud se v banky/ něco změnilo, commitnout a pushnout do vlastního forku (origin)
        status_res = subprocess.run(
            ["git", "status", "--porcelain", "--", "banky"],
            cwd=BASE, capture_output=True, text=True, timeout=15
        )
        if status_res.stdout.strip():
            subprocess.run(["git", "add", "banky"], cwd=BASE, capture_output=True, text=True, timeout=15)
            subprocess.run(
                ["git", "commit", "-m", "chore(banky): auto-sync question banks from upstream/main"],
                cwd=BASE, capture_output=True, text=True, timeout=15
            )
            push_res = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=BASE, capture_output=True, text=True, timeout=30
            )
            out = (out + f"\n[Auto-sync] Nové banky uloženy a pushnuty do origin/main ({push_res.returncode}).").strip()
        else:
            out = "Banky otázek jsou aktuální."

        print(f"[Auto-sync] Výsledek: {out}")
        return out
    except Exception as e:
        print(f"[Auto-sync] Chyba: {e}")
        return str(e)


def sync_worker():
    while True:
        time.sleep(15 * 60)
        git_pull()


threading.Thread(target=sync_worker, daemon=True).start()


# --- Session Helpers ---
def create_session_token(user: Dict[str, Any]) -> str:
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user.get("role", "student"),
        "theme": user.get("theme", "games"),
        "ts": int(time.time())
    }
    return serializer.dumps(payload)


def verify_session_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE)
    return verify_session_token(token)


def require_user(request: Request) -> Dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nejste přihlášeni")
    return user


def require_admin(request: Request) -> Dict[str, Any]:
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pouze pro administrátora")
    return user


# --- FastAPI Application ---
app = FastAPI(title="TZI Trenér", docs_url=None, redoc_url=None)


# --- HTML Templates (Login, Register, Admin) ---
LOGIN_REGISTER_HTML = """<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TZI Trenér - Vstup</title>
    <style>
        :root {
            --bg: #1e1e2e;
            --card: #181825;
            --border: #313244;
            --text: #cdd6f4;
            --text-dim: #a6adc8;
            --mauve: #cba6f7;
            --mauve-hover: #b4befe;
            --pink: #f5c2e7;
            --error: #f38ba8;
            --green: #a6e3a1;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 1.5rem;
        }
        .auth-card {
            background-color: var(--card);
            border: 1px solid var(--border);
            border-radius: 1.25rem;
            padding: 2.5rem;
            width: 100%;
            max-width: 440px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4);
            text-align: center;
        }
        .icon {
            font-size: 3rem;
            margin-bottom: 0.8rem;
            display: inline-block;
        }
        h1 {
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
            color: var(--mauve);
        }
        p.subtitle {
            color: var(--text-dim);
            font-size: 0.95rem;
            margin-bottom: 1.8rem;
        }
        .tabs {
            display: flex;
            background: #11111b;
            border-radius: 0.75rem;
            padding: 0.3rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }
        .tab-btn {
            flex: 1;
            padding: 0.6rem;
            background: transparent;
            border: none;
            color: var(--text-dim);
            font-weight: 600;
            font-size: 0.95rem;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .tab-btn.active {
            background: var(--mauve);
            color: #11111b;
        }
        .form-group {
            margin-bottom: 1.2rem;
            text-align: left;
        }
        label {
            display: block;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 0.4rem;
            color: var(--text-dim);
        }
        input, select {
            width: 100%;
            padding: 0.8rem 1rem;
            background: #11111b;
            border: 1px solid var(--border);
            border-radius: 0.6rem;
            color: var(--text);
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        input:focus, select:focus {
            border-color: var(--mauve);
            box-shadow: 0 0 0 3px rgba(203, 166, 247, 0.2);
        }
        button.submit-btn {
            width: 100%;
            padding: 0.85rem 1rem;
            background: var(--mauve);
            color: #11111b;
            border: none;
            border-radius: 0.6rem;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 0.5rem;
        }
        button.submit-btn:hover {
            background: var(--mauve-hover);
        }
        .error-msg {
            background: rgba(243, 139, 168, 0.15);
            border: 1px solid var(--error);
            color: var(--error);
            padding: 0.75rem;
            border-radius: 0.5rem;
            font-size: 0.9rem;
            margin-bottom: 1.2rem;
        }
        .success-msg {
            background: rgba(166, 227, 161, 0.15);
            border: 1px solid var(--green);
            color: var(--green);
            padding: 0.75rem;
            border-radius: 0.5rem;
            font-size: 0.9rem;
            margin-bottom: 1.2rem;
        }
        .notice {
            font-size: 0.8rem;
            color: var(--text-dim);
            margin-top: 1.2rem;
            line-height: 1.4;
        }
    </style>
</head>
<body>
    <main class="auth-card">
        <header>
            <div class="icon">🎓</div>
            <h1>TZI Trenér</h1>
            <p class="subtitle">Teoretická informatika (KI/TIN)</p>
        </header>

        <!--MESSAGE-->

        <nav class="tabs" aria-label="Volba přihlášení nebo registrace">
            <button class="tab-btn <!--LOGIN_ACTIVE-->" onclick="switchTab('login')">Přihlášení</button>
            <button class="tab-btn <!--REG_ACTIVE-->" onclick="switchTab('reg')">Registrace</button>
        </nav>

        <section id="login-form" style="display: <!--LOGIN_DISPLAY-->;">
            <form method="POST" action="/login">
                <div class="form-group">
                    <label>Uživatelské jméno</label>
                    <input type="text" name="username" placeholder="Zadejte své jméno..." required autofocus>
                </div>
                <div class="form-group">
                    <label>Heslo</label>
                    <input type="password" name="password" placeholder="Zadejte heslo..." required>
                </div>
                <button type="submit" class="submit-btn">Přihlásit se</button>
            </form>
        </section>

        <section id="reg-form" style="display: <!--REG_DISPLAY-->;">
            <form method="POST" action="/register">
                <div class="form-group">
                    <label>Uživatelské jméno</label>
                    <input type="text" name="username" placeholder="Zvolte si přezdívku..." required minlength="2">
                </div>
                <div class="form-group">
                    <label>Heslo</label>
                    <input type="password" name="password" placeholder="Min. 4 znaky" required minlength="4">
                </div>
                <div class="form-group">
                    <label>Potvrzení hesla</label>
                    <input type="password" name="password_confirm" placeholder="Zopakujte heslo..." required minlength="4">
                </div>
                <button type="submit" class="submit-btn">Zaregistrovat se</button>
            </form>
        </section>

        <nav style="margin-top: 1.5rem; padding-top: 1.2rem; border-top: 1px solid var(--border);" aria-label="Zkušební přístup">
            <a href="/trial" style="display:block; text-decoration:none; background:#11111b; border:1px solid var(--border); color:var(--text-dim); padding:0.75rem; border-radius:0.6rem; font-weight:600; font-size:0.9rem; text-align:center; transition:all 0.2s;">
                🚀 Vyzkoušet bez přihlášení (Trial mód)
            </a>
        </nav>

        <footer style="margin-top: 1.2rem; font-size: 0.75rem; color: var(--text-dim); text-align: center; line-height: 1.5;">
            Made with AI · Poděkování <b>Zdenax</b> za vytvoření apky · <a href="https://github.com/zdenax/TZI-TIN-APP" target="_blank" rel="noopener noreferrer" style="color: var(--text-dim); text-decoration: underline;">GitHub: TZI-TIN-APP</a>
        </footer>
    </main>

    <script>
        function switchTab(t) {
            document.getElementById('login-form').style.display = t === 'login' ? 'block' : 'none';
            document.getElementById('reg-form').style.display = t === 'reg' ? 'block' : 'none';
            const btns = document.querySelectorAll('.tab-btn');
            btns[0].classList.toggle('active', t === 'login');
            btns[1].classList.toggle('active', t === 'reg');
        }
    </script>
</body>
</html>
"""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TZI Trenér - Admin Panel</title>
    <style>
        :root {
            --bg: #1e1e2e;
            --card: #181825;
            --border: #313244;
            --text: #cdd6f4;
            --text-dim: #a6adc8;
            --mauve: #cba6f7;
            --green: #a6e3a1;
            --yellow: #f9e2af;
            --red: #f38ba8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 2rem 1rem;
            max-width: 900px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1rem;
            flex-wrap: wrap;
            gap: 1rem;
        }
        h1 { font-size: 1.8rem; color: var(--mauve); }
        .header-actions {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            flex-wrap: wrap;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            white-space: nowrap;
            background: var(--mauve);
            color: #11111b;
            padding: 0.6rem 1.2rem;
            border-radius: 0.5rem;
            text-decoration: none;
            font-weight: 700;
            border: none;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.9; }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .card h2 { font-size: 1.3rem; margin-bottom: 1rem; color: var(--text); }
        .code-box {
            background: #11111b;
            border: 2px dashed var(--mauve);
            padding: 1rem;
            border-radius: 0.6rem;
            font-family: monospace;
            font-size: 1.4rem;
            color: var(--green);
            text-align: center;
            letter-spacing: 2px;
            margin: 1rem 0;
            user-select: all;
            overflow-wrap: anywhere;
        }
        .table-wrap {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin-top: 1rem;
            border-radius: 0.5rem;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 580px;
        }
        th, td {
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }
        th { color: var(--text-dim); font-size: 0.85rem; text-transform: uppercase; }
        tr:hover { background: rgba(255, 255, 255, 0.02); }
        .badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 1rem;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .badge-admin { background: rgba(203, 166, 247, 0.2); color: var(--mauve); }
        .badge-student { background: rgba(166, 227, 161, 0.2); color: var(--green); }
        @media (max-width: 600px) {
            body { padding: 1.25rem 0.75rem; }
            h1 { font-size: 1.4rem; }
            header { flex-direction: column; align-items: flex-start; gap: 0.8rem; }
            .header-actions { width: 100%; }
            .header-actions .btn { flex: 1; text-align: center; }
            .card { padding: 1rem; }
            .code-box { font-size: 1.1rem; padding: 0.75rem; }
        }
    </style>
</head>
<body>
    <header>
        <div>
            <h1>🛡️ TZI Admin Panel</h1>
            <p style="color:var(--text-dim); font-size:0.9rem;">Správa kódů a přehled studentů</p>
        </div>
        <div class="header-actions">
            <a href="/" class="btn" style="background:var(--border); color:var(--text);">Zpět do trenéra</a>
            <a href="/logout" class="btn" style="background:var(--red); color:#11111b;">Odhlásit</a>
        </div>
    </header>

    <!--GENERATED_CODE_SECTION-->

    <div class="card">
        <h2>🎫 Generátor jednorázových kódů</h2>
        <p style="color:var(--text-dim); font-size:0.95rem;">Každý vygenerovaný kód může použít právě jeden spolužák k registraci. Kód se v databázi uloží jako bezpečný hash.</p>
        <form method="POST" action="/admin/invite" style="margin-top:1rem;">
            <button type="submit" class="btn">✨ Vygenerovat nový kód pozvánky</button>
        </form>
    </div>

    <div class="card">
        <h2>👥 Registrovaní studenti & Žebříček</h2>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Pořadí</th>
                        <th>Přezdívka</th>
                        <th>Téma</th>
                        <th>Body</th>
                        <th>Aktuální Streak</th>
                        <th>Nejlepší Streak</th>
                        <th>Role</th>
                    </tr>
                </thead>
                <tbody>
                    <!--USERS_ROWS-->
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""


# --- Authentication & Registration Endpoints ---
@app.get("/login", response_class=HTMLResponse)
def get_login(error: Optional[str] = None, success: Optional[str] = None):
    msg = ""
    if error:
        msg = f'<div class="error-msg">{error}</div>'
    elif success:
        msg = f'<div class="success-msg">{success}</div>'

    html = LOGIN_REGISTER_HTML.replace("<!--MESSAGE-->", msg)
    html = html.replace("<!--LOGIN_ACTIVE-->", "active")
    html = html.replace("<!--REG_ACTIVE-->", "")
    html = html.replace("<!--LOGIN_DISPLAY-->", "block")
    html = html.replace("<!--REG_DISPLAY-->", "none")
    return html


@app.post("/login")
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


@app.get("/register", response_class=HTMLResponse)
def get_register(error: Optional[str] = None):
    msg = f'<div class="error-msg">{error}</div>' if error else ""
    html = LOGIN_REGISTER_HTML.replace("<!--MESSAGE-->", msg)
    html = html.replace("<!--LOGIN_ACTIVE-->", "")
    html = html.replace("<!--REG_ACTIVE-->", "active")
    html = html.replace("<!--LOGIN_DISPLAY-->", "none")
    html = html.replace("<!--REG_DISPLAY-->", "block")
    return html


@app.post("/register")
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


@app.get("/trial")
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


@app.get("/logout")
def get_logout(response: Response):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# --- Admin Panel Endpoints ---
@app.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request, user: Dict[str, Any] = Depends(require_admin), new_code: Optional[str] = None):
    code_section = ""
    if new_code:
        code_section = f"""
        <div class="card" style="border-color:var(--green);">
            <h2 style="color:var(--green);">🎉 Nový kód vygenerován!</h2>
            <p>Zkopíruj tento kód a předej ho spolužákovi k jednorázové registraci:</p>
            <div class="code-box">{new_code}</div>
            <p style="font-size:0.85rem; color:var(--text-dim);">Kód je v databázi bezpečně zahashován a po použití automaticky zanikne.</p>
        </div>
        """

    students = scoring.get_admin_leaderboard()
    rows = ""
    for idx, s in enumerate(students, 1):
        role_badge = f'<span class="badge badge-{s["role"]}">{s["role"]}</span>'
        rows += f"""
        <tr>
            <td><b>#{idx}</b></td>
            <td><b>{s['username']}</b></td>
            <td>{s.get('theme', 'games')}</td>
            <td><b style="color:var(--mauve);">{s.get('total_points') or 0} b.</b></td>
            <td>🔥 {s.get('current_streak') or 0}</td>
            <td>⭐ {s.get('best_streak') or 0}</td>
            <td>{role_badge}</td>
        </tr>
        """

    html = ADMIN_HTML.replace("<!--GENERATED_CODE_SECTION-->", code_section)
    html = html.replace("<!--USERS_ROWS-->", rows if rows else "<tr><td colspan='7'>Žádní studenti zatím nejsou registrováni.</td></tr>")
    return html


@app.post("/admin/invite")
def post_admin_invite(user: Dict[str, Any] = Depends(require_admin)):
    code = db.create_invite_code()
    return RedirectResponse(url=f"/admin?new_code={code}", status_code=303)


# --- API Endpoints ---
@app.get("/api/me")
def api_me(user: Dict[str, Any] = Depends(require_user)):
    if user.get("role") == "trial" or user.get("user_id") == 0:
        return {
            "user_id": 0,
            "username": "Host (Trial)",
            "role": "trial",
            "theme": "catppuccin",
            "points": 0,
            "streak": 0,
            "best_streak": 0,
            "daily_streak": 0,
            "best_daily_streak": 0,
            "daily_goal": scoring.DAILY_MIN_GOAL,
            "questions_today": 0,
            "daily_goal_met": False,
            "rank": "-",
            "total_users": "-"
        }
    user_db = db.get_user_by_id(user["user_id"])
    stats = scoring.get_user_leaderboard_position(user["user_id"])
    return {
        "user_id": user["user_id"],
        "username": user_db["username"] if user_db else user["username"],
        "role": user.get("role", "student"),
        "theme": user_db.get("theme", "games") if user_db else "games",
        "points": stats["points"],
        "streak": stats["current_streak"],
        "best_streak": stats["best_streak"],
        "daily_streak": stats["daily_streak"],
        "best_daily_streak": stats["best_daily_streak"],
        "daily_goal": stats["daily_goal"],
        "questions_today": stats["questions_today"],
        "daily_goal_met": stats["daily_goal_met"],
        "rank": stats["rank"],
        "total_users": stats["total"]
    }


@app.get("/api/daily-progress")
def api_daily_progress(user: Dict[str, Any] = Depends(require_user)):
    if user.get("role") == "trial" or user.get("user_id") == 0:
        return {
            "date": "",
            "questions_answered": 0,
            "questions_correct": 0,
            "daily_goal": scoring.DAILY_MIN_GOAL,
            "goal_met": False,
            "daily_streak": 0,
            "best_daily_streak": 0,
            "last_goal_date": None,
            "history": []
        }
    return scoring.get_daily_progress(user["user_id"])


@app.get("/api/sources")
def api_sources(user: Dict[str, Any] = Depends(require_user)):
    srcs = tzi_trener.list_sources()
    real = [s for s in srcs if s["id"] != tzi_trener.ALL]
    default = real[-1]["id"] if real else ""
    return {"sources": srcs, "default": default}


@app.get("/api/questions")
def api_questions(source: str = "", user: Dict[str, Any] = Depends(require_user)):
    try:
        return tzi_trener.load_questions(source)
    except (KeyError, OSError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/recall")
def api_recall(user: Dict[str, Any] = Depends(require_user)):
    try:
        return tzi_trener.load_recall()
    except (KeyError, OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/progress")
def api_get_progress(source: str = "", user: Dict[str, Any] = Depends(require_user)):
    user_id = user["user_id"]
    if user.get("role") == "trial" or user_id == 0:
        return {"seen": {}, "session": None}

    conn = db.get_db()

    # 1. Získat celkový agregovaný přehled 'seen' ze všech přednášek
    all_seen = {}
    rows = conn.execute("SELECT seen_json FROM user_progress WHERE user_id = ?", (user_id,)).fetchall()
    for r in rows:
        try:
            d = json.loads(r["seen_json"])
            all_seen.update(d)
        except Exception:
            pass

    # 2. Získat session pro konkrétní zvolený zdroj
    active_session = None
    if source:
        row = conn.execute(
            "SELECT session_json FROM user_progress WHERE user_id = ? AND source = ?",
            (user_id, source)
        ).fetchone()
        if row and row["session_json"]:
            try:
                active_session = json.loads(row["session_json"])
            except Exception:
                pass

    return {"seen": all_seen, "session": active_session}


# --- Question Caching & Anti-Spoofing Verification ---
ALL_QUESTIONS: Dict[str, Dict[str, Any]] = {}

def refresh_questions():
    global ALL_QUESTIONS
    try:
        qs = tzi_trener.load_questions(tzi_trener.ALL) + tzi_trener.load_recall()
        ALL_QUESTIONS = {str(q["id"]): q for q in qs}
    except Exception as e:
        print(f"[Warning] Failed to pre-cache questions: {e}")

refresh_questions()

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")

def norm_str(s: str) -> str:
    cleaned = strip_accents(str(s).lower())
    return " ".join("".join(c if c.isalnum() else " " for c in cleaned).split())

def lev1(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1: return False
    if len(a) == len(b): return sum(1 for x, y in zip(a, b) if x != y) == 1
    if len(a) > len(b): a, b = b, a
    for i in range(len(b)):
        if b[:i] + b[i+1:] == a: return True
    return False

def verify_answer(q: Dict[str, Any], user_answer: Any) -> bool:
    if not q or user_answer is None:
        return False
    q_type = q.get("type", "choice")
    if q_type == "choice":
        correct = set(str(k) for k in q.get("correct", []))
        if isinstance(user_answer, list):
            u_set = set(str(k) for k in user_answer)
        else:
            u_set = {str(user_answer)}
        return len(correct) > 0 and u_set == correct
    elif q_type == "input":
        expected = norm_str(q.get("answer", ""))
        val = user_answer[0] if isinstance(user_answer, list) and user_answer else user_answer
        given = norm_str(val)
        return given == expected or given.replace(" ", "") == expected.replace(" ", "")
    elif q_type == "recall":
        val = user_answer[0] if isinstance(user_answer, list) and user_answer else user_answer
        given = norm_str(val)
        if not given:
            return False
        for acc in q.get("accept", []):
            exp = norm_str(acc)
            if given == exp:
                return True
            gw = given.split()
            ew = exp.split()
            if len(gw) == len(ew) and all(x == y or (len(y) > 5 and x[0] == y[0] and lev1(x, y)) for x, y in zip(gw, ew)):
                return True
        return False
    return False


@app.post("/api/progress")
async def api_post_progress(request: Request, source: str = "", user: Dict[str, Any] = Depends(require_user)):
    user_id = user["user_id"]
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")

    # Pokud jde o Trial mód, nic neukládáme do databáze a nepočítáme globální skóre
    if user.get("role") == "trial" or user_id == 0:
        return {"ok": True, "score": None}

    seen = payload.get("seen", {})
    session = payload.get("session")
    latest_answer = payload.get("latest")

    # Pokud klient poslal explicitní informaci o poslední zodpovězené otázce
    score_result = None
    if latest_answer and isinstance(latest_answer, dict) and "id" in latest_answer:
        q_id = str(latest_answer["id"])
        q = ALL_QUESTIONS.get(q_id)
        u_ans = latest_answer.get("userKeys") or latest_answer.get("user_answer")
        # Anti-spoofing: server verifikuje odpověď proti bankám
        if q and u_ans is not None:
            is_correct = verify_answer(q, u_ans)
        else:
            is_correct = bool(latest_answer.get("isCorrect"))
        score_result = scoring.record_question_answer(user_id, q_id, is_correct)

    # Uložit stav do user_progress
    conn = db.get_db()
    with conn:
        conn.execute(
            """
            INSERT INTO user_progress (user_id, source, seen_json, session_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, source) DO UPDATE SET
                seen_json = excluded.seen_json,
                session_json = excluded.session_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, source or "_default", json.dumps(seen, ensure_ascii=False), json.dumps(session, ensure_ascii=False) if session else None)
        )

    return {"ok": True, "score": score_result}


@app.post("/api/sync")
async def api_sync(request: Request, user: Dict[str, Any] = Depends(require_user)):
    """Offline synchronizace: dávkové bezpečné zpracování odpovědí vyřešených offline s anti-spoofing kontrolou."""
    user_id = user["user_id"]
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")

    if user.get("role") == "trial" or user_id == 0:
        return {"ok": True, "synced_count": 0, "points_awarded": 0, "leaderboard": None}

    answers = payload.get("answers", [])
    if not isinstance(answers, list):
        raise HTTPException(status_code=400, detail="answers musí být list")

    # Anti-spoofing limit na velikost jedné dávky
    if len(answers) > 100:
        answers = answers[:100]

    seen = payload.get("seen", {})
    source = payload.get("source", "_default")

    total_points_gained = 0
    synced_count = 0
    seen_ids = set()

    for item in answers:
        if not isinstance(item, dict):
            continue
        q_id = str(item.get("id", ""))
        if not q_id or q_id in seen_ids:
            continue
        seen_ids.add(q_id)

        q = ALL_QUESTIONS.get(q_id)
        if not q:
            continue

        u_ans = item.get("user_answer") or item.get("userKeys")
        if u_ans is None:
            continue

        # Anti-spoofing: přísná validace serverem
        is_correct = verify_answer(q, u_ans)
        res = scoring.record_question_answer(user_id, q_id, is_correct)
        if res and res.get("points_awarded", 0) > 0:
            total_points_gained += res["points_awarded"]
        synced_count += 1

    if seen:
        conn = db.get_db()
        with conn:
            conn.execute(
                """
                INSERT INTO user_progress (user_id, source, seen_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, source) DO UPDATE SET
                    seen_json = excluded.seen_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, source, json.dumps(seen, ensure_ascii=False))
            )

    pos = scoring.get_user_leaderboard_position(user_id)
    return {
        "ok": True,
        "synced_count": synced_count,
        "points_awarded": total_points_gained,
        "leaderboard": pos
    }


# --- PWA & WASM Endpoints ---
@app.get("/quiz.wasm")
def get_quiz_wasm():
    return FileResponse(tzi_trener.UI_DIR / "quiz.wasm", media_type="application/wasm", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/manifest.webmanifest")
def get_manifest():
    return FileResponse(tzi_trener.UI_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def get_sw():
    return FileResponse(tzi_trener.UI_DIR / "sw.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/icon.svg")
def get_icon():
    return FileResponse(tzi_trener.UI_DIR / "icon.svg", media_type="image/svg+xml")


@app.get("/api/leaderboard")
def api_leaderboard(user: Dict[str, Any] = Depends(require_user)):
    rows = scoring.get_admin_leaderboard()
    top_list = [
        {
            "username": r["username"],
            "points": r.get("total_points") or 0,
            "current_streak": r.get("current_streak") or 0,
            "best_streak": r.get("best_streak") or 0,
            "daily_streak": r.get("daily_streak") or 0,
        }
        for r in rows[:30]
    ]
    if user.get("role") == "trial" or user["user_id"] == 0:
        return {"rank": "-", "total": len(rows), "points": 0, "current_streak": 0, "best_streak": 0, "leaderboard": top_list}
    pos = scoring.get_user_leaderboard_position(user["user_id"])
    pos["leaderboard"] = top_list
    return pos


@app.get("/api/account/recap")
def api_account_recap(user: Dict[str, Any] = Depends(require_user)):
    srcs = tzi_trener.list_sources()
    if user.get("role") == "trial" or user["user_id"] == 0:
        return {
            "username": "Host (Trial)",
            "role": "trial",
            "created_at": None,
            "sources": [{"id": s["id"], "title": s.get("title", s["id"]), "total": s.get("count", 0), "correct": 0, "wrong": 0} for s in srcs],
            "total_questions": sum(s.get("count", 0) for s in srcs),
            "total_correct": 0,
            "total_wrong": 0,
        }
    uid = user["user_id"]
    u_info = db.get_user_by_id(uid) or {}
    prog_map = db.get_user_all_progress_map(uid)
    merged_seen: Dict[str, str] = {}
    for _, smap in prog_map.items():
        for qid, st in smap.items():
            merged_seen[str(qid)] = st

    source_breakdown = []
    total_q = 0
    total_c = 0
    total_w = 0
    for s in srcs:
        sid = s["id"]
        try:
            bank = tzi_trener.load_questions(sid)
            qs = [q for q in bank.get("questions", []) if not q.get("reveal")]
        except Exception:
            qs = []
        s_seen = prog_map.get(sid, {})
        c_cnt = sum(1 for q in qs if (s_seen.get(str(q["id"])) or merged_seen.get(str(q["id"]))) == "correct")
        w_cnt = sum(1 for q in qs if (s_seen.get(str(q["id"])) or merged_seen.get(str(q["id"]))) == "wrong")
        q_cnt = len(qs)
        total_q += q_cnt
        total_c += c_cnt
        total_w += w_cnt
        source_breakdown.append({
            "id": sid,
            "title": s.get("title", sid),
            "total": q_cnt,
            "correct": c_cnt,
            "wrong": w_cnt,
        })

    return {
        "username": u_info.get("username", user.get("username", "")),
        "role": u_info.get("role", user.get("role", "student")),
        "created_at": u_info.get("created_at"),
        "sources": source_breakdown,
        "total_questions": total_q,
        "total_correct": total_c,
        "total_wrong": total_w,
    }


@app.post("/api/account/username")
async def api_account_username(request: Request, user: Dict[str, Any] = Depends(require_user)):
    if user.get("role") == "trial" or user["user_id"] == 0:
        raise HTTPException(status_code=403, detail="V Trial režimu nelze měnit jméno účtu.")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný požadavek.")
    new_username = str(body.get("username") or "").strip()
    ok, err, updated_user = db.update_username(user["user_id"], new_username)
    if not ok or not updated_user:
        raise HTTPException(status_code=400, detail=err or "Změna jména selhala.")
    token = create_session_token(updated_user)
    resp = JSONResponse({"ok": True, "username": updated_user["username"]})
    resp.set_cookie(SESSION_COOKIE, token, max_age=86400 * 30, httponly=True, samesite="lax")
    return resp


@app.post("/api/account/password")
async def api_account_password(request: Request, user: Dict[str, Any] = Depends(require_user)):
    if user.get("role") == "trial" or user["user_id"] == 0:
        raise HTTPException(status_code=403, detail="V Trial režimu nelze měnit heslo.")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný požadavek.")
    cur_pw = str(body.get("current_password") or "")
    new_pw = str(body.get("new_password") or "")
    new_pw2 = str(body.get("new_password_confirm") or "")
    if new_pw != new_pw2:
        raise HTTPException(status_code=400, detail="Nová hesla se neshodují.")
    ok, err = db.update_password(user["user_id"], cur_pw, new_pw)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Změna hesla selhala.")
    return {"ok": True}


@app.post("/api/account/revalidate-delete")
async def api_account_revalidate_delete(request: Request, user: Dict[str, Any] = Depends(require_user)):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný požadavek.")
    password = str(body.get("password") or "")
    scope = str(body.get("scope") or "source")
    source = str(body.get("source") or "")

    if user.get("role") == "trial" or user["user_id"] == 0:
        if password.strip().upper() != "SMAZAT":
            raise HTTPException(status_code=403, detail="Pro potvrzení v Trial režimu napište SMAZAT.")
        return {"ok": True, "scope": scope, "source": source}

    if not db.verify_user_password(user["user_id"], password):
        raise HTTPException(status_code=403, detail="Neplatné heslo. Mazání dat bylo zamítnuto.")

    if scope == "all":
        db.clear_user_progress_db(user["user_id"], "_all")
    else:
        db.clear_user_progress_db(user["user_id"], source or "_default")

    return {"ok": True, "scope": scope, "source": source}


@app.post("/api/account/delete-profile")
async def api_account_delete_profile(request: Request, user: Dict[str, Any] = Depends(require_user)):
    if user.get("role") == "trial" or user["user_id"] == 0:
        raise HTTPException(status_code=403, detail="Trial profile cannot be deleted.")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    step1_ack = bool(body.get("step1_ack"))
    confirm_username = str(body.get("confirm_username") or "").strip()
    confirm_phrase = str(body.get("confirm_phrase") or "").strip().upper()
    password = str(body.get("password") or "")

    u_db = db.get_user_by_id(user["user_id"])
    actual_username = u_db["username"] if u_db else user.get("username", "")

    if not step1_ack:
        raise HTTPException(status_code=400, detail="Step 1 confirmation checkbox is required.")
    if confirm_username != actual_username:
        raise HTTPException(status_code=400, detail="Entered username does not match your account username.")
    if confirm_phrase != "DELETE":
        raise HTTPException(status_code=400, detail="Confirmation phrase must be DELETE.")
    if not db.verify_user_password(user["user_id"], password):
        raise HTTPException(status_code=403, detail="Invalid account password.")

    db.delete_user_account(user["user_id"])
    resp = JSONResponse({"ok": True, "redirect": "/login"})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# --- King of the Hill (FFA / 1v1) Endpoints ---
@app.get("/api/koth/status")
def api_koth_status(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_koth_status()


@app.get("/api/koth/leaderboard")
def api_koth_leaderboard(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_koth_status()


@app.post("/api/koth/start")
async def api_koth_start(request: Request, user: Dict[str, Any] = Depends(require_user)):
    import random
    count = scoring.KOTH_DEFAULT_QUESTIONS
    source = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            count = max(1, min(30, int(body.get("count", count))))
            source = str(body.get("source", ""))
    except Exception:
        pass

    try:
        pool = tzi_trener.load_questions(source or tzi_trener.ALL)
    except Exception:
        pool = list(ALL_QUESTIONS.values())

    eligible = [q for q in pool if not q.get("reveal")]
    picked = random.sample(eligible, min(count, len(eligible))) if eligible else []
    status = scoring.get_koth_status()
    return {
        "ok": True,
        "questions": picked,
        "king": status["king"],
        "status": status
    }


@app.post("/api/koth/submit")
async def api_koth_submit(request: Request, user: Dict[str, Any] = Depends(require_user)):
    user_id = user["user_id"]
    if user.get("role") == "trial" or user_id == 0:
        raise HTTPException(status_code=403, detail="Pro souboj o Krále kopce je nutné se přihlásit.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")

    user_db = db.get_user_by_id(user_id)
    username = user_db["username"] if user_db else user.get("username", "Student")

    answers = payload.get("answers", [])
    time_ms = int(payload.get("time_ms", 0) or 0)
    explicit_score = payload.get("score")

    correct_count = 0
    total_q = len(answers) if isinstance(answers, list) and len(answers) > 0 else int(payload.get("total_questions", scoring.KOTH_DEFAULT_QUESTIONS))

    if isinstance(answers, list) and len(answers) > 0:
        for item in answers:
            if not isinstance(item, dict):
                continue
            q_id = str(item.get("id", ""))
            q = ALL_QUESTIONS.get(q_id)
            u_ans = item.get("userKeys") if item.get("userKeys") is not None else item.get("user_answer")
            if q and u_ans is not None:
                is_ok = verify_answer(q, u_ans)
            else:
                is_ok = bool(item.get("isCorrect", False))
            if is_ok:
                correct_count += 1
            if q_id:
                scoring.record_question_answer(user_id, q_id, is_ok)
    elif "correct_count" in payload:
        correct_count = int(payload.get("correct_count", 0))

    return scoring.submit_koth_challenge(
        user_id=user_id,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms,
        explicit_score=explicit_score
    )


def _evaluate_competitive_submission(user_id: int, payload: Dict[str, Any]):
    answers = payload.get("answers", [])
    time_ms = int(payload.get("time_ms", 0) or 0)
    explicit_score = payload.get("score")
    correct_count = 0
    total_q = len(answers) if isinstance(answers, list) and len(answers) > 0 else int(payload.get("total_questions", scoring.KOTH_DEFAULT_QUESTIONS))
    question_ids = []

    if isinstance(answers, list) and len(answers) > 0:
        for item in answers:
            if not isinstance(item, dict):
                continue
            q_id = str(item.get("id", ""))
            if q_id:
                question_ids.append(q_id)
            q = ALL_QUESTIONS.get(q_id)
            u_ans = item.get("userKeys") if item.get("userKeys") is not None else item.get("user_answer")
            if q and u_ans is not None:
                is_ok = verify_answer(q, u_ans)
            else:
                is_ok = bool(item.get("isCorrect", False))
            if is_ok:
                correct_count += 1
            if q_id:
                scoring.record_question_answer(user_id, q_id, is_ok)
    elif "correct_count" in payload:
        correct_count = int(payload.get("correct_count", 0))

    return correct_count, total_q, time_ms, explicit_score, question_ids


@app.get("/api/competitive/overview")
def api_competitive_overview(user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    return {
        "ffa": scoring.get_ffa_status(),
        "duel": scoring.get_duel_status(uid),
        "koth": scoring.get_koth_status(),
        "rooms": scoring.list_comp_rooms(uid)
    }


def _resolve_room_questions(room: Optional[Dict[str, Any]]) -> list:
    if not room:
        return []
    q_ids = room.get("question_ids") or []
    picked = [ALL_QUESTIONS[str(qid)] for qid in q_ids if str(qid) in ALL_QUESTIONS]
    if not picked:
        import random
        src = room.get("source") or ""
        cnt = int(room.get("question_count") or scoring.KOTH_DEFAULT_QUESTIONS)
        try:
            pool = tzi_trener.load_questions(src or tzi_trener.ALL)
        except Exception:
            pool = list(ALL_QUESTIONS.values())
        eligible = [q for q in pool if not q.get("reveal")]
        picked = random.sample(eligible, min(cnt, len(eligible))) if eligible else []
    return picked


@app.get("/api/rooms")
def api_rooms_list(user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    return scoring.list_comp_rooms(uid)


@app.post("/api/rooms/create")
async def api_rooms_create(request: Request, user: Dict[str, Any] = Depends(require_user)):
    import random
    uid = user.get("user_id") or 0
    if user.get("role") == "trial" or uid == 0:
        raise HTTPException(status_code=403, detail="Pro vytvoření místnosti v lobby je nutné se přihlásit.")

    mode = "ffa"
    name = ""
    count = scoring.KOTH_DEFAULT_QUESTIONS
    source = ""
    max_players = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            mode = str(body.get("mode", "ffa"))
            name = str(body.get("name", ""))
            count = max(1, min(30, int(body.get("count", count))))
            source = str(body.get("source", ""))
            if body.get("max_players") is not None:
                max_players = int(body.get("max_players"))
    except Exception:
        pass

    try:
        pool = tzi_trener.load_questions(source or tzi_trener.ALL)
    except Exception:
        pool = list(ALL_QUESTIONS.values())
    eligible = [q for q in pool if not q.get("reveal")]
    picked = random.sample(eligible, min(count, len(eligible))) if eligible else []
    q_ids = [str(q["id"]) for q in picked if "id" in q]

    user_db = db.get_user_by_id(uid)
    username = user_db["username"] if user_db else user.get("username", "Student")

    room = scoring.create_comp_room(
        user_id=uid,
        username=username,
        mode=mode,
        name=name,
        question_count=len(picked) or count,
        source=source,
        question_ids=q_ids,
        max_players=max_players,
    )
    return {"ok": True, "room": room, "questions": picked}


@app.get("/api/rooms/{room_id}")
def api_room_detail(room_id: int, user: Dict[str, Any] = Depends(require_user)):
    room = scoring.get_comp_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Místnost neexistuje.")
    questions = _resolve_room_questions(room) if room.get("status") in ("in_progress", "completed") else []
    return {"ok": True, "room": room, "questions": questions}


@app.post("/api/rooms/{room_id}/join")
async def api_room_join(room_id: int, request: Request, user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    if user.get("role") == "trial" or uid == 0:
        raise HTTPException(status_code=403, detail="Pro připojení do místnosti je nutné se přihlásit.")

    auto_start_duel = False
    try:
        body = await request.json()
        if isinstance(body, dict):
            auto_start_duel = bool(body.get("auto_start_duel", False))
    except Exception:
        pass

    user_db = db.get_user_by_id(uid)
    username = user_db["username"] if user_db else user.get("username", "Student")
    res = scoring.join_comp_room(room_id, uid, username, auto_start_duel=auto_start_duel)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Nelze se připojit do místnosti."))
    room = res["room"]
    questions = _resolve_room_questions(room) if room.get("status") == "in_progress" else []
    return {"ok": True, "room": room, "questions": questions}


@app.post("/api/rooms/{room_id}/start")
def api_room_start(room_id: int, user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    if user.get("role") == "trial" or uid == 0:
        raise HTTPException(status_code=403, detail="Nepřihlášený uživatel nemůže spustit místnost.")
    res = scoring.start_comp_room(room_id, uid)
    if not res.get("ok"):
        raise HTTPException(status_code=403, detail=res.get("error", "Nelze spustit místnost."))
    room = res["room"]
    questions = _resolve_room_questions(room)
    return {"ok": True, "room": room, "questions": questions}


@app.post("/api/rooms/{room_id}/leave")
def api_room_leave(room_id: int, user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    return scoring.leave_comp_room(room_id, uid)


@app.post("/api/rooms/{room_id}/submit")
async def api_room_submit(room_id: int, request: Request, user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    if user.get("role") == "trial" or uid == 0:
        raise HTTPException(status_code=403, detail="Pro odeslání výsledku v místnosti je nutné se přihlásit.")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")

    user_db = db.get_user_by_id(uid)
    username = user_db["username"] if user_db else user.get("username", "Student")
    correct_count, total_q, time_ms, explicit_score, _ = _evaluate_competitive_submission(uid, payload)
    res = scoring.submit_comp_room_result(
        room_id=room_id,
        user_id=uid,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms,
        explicit_score=explicit_score,
    )
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Místnost neexistuje."))
    return res


@app.get("/api/ffa/status")
def api_ffa_status(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_ffa_status()


@app.post("/api/ffa/start")
async def api_ffa_start(request: Request, user: Dict[str, Any] = Depends(require_user)):
    import random
    count = scoring.KOTH_DEFAULT_QUESTIONS
    source = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            count = max(1, min(30, int(body.get("count", count))))
            source = str(body.get("source", ""))
    except Exception:
        pass
    try:
        pool = tzi_trener.load_questions(source or tzi_trener.ALL)
    except Exception:
        pool = list(ALL_QUESTIONS.values())
    eligible = [q for q in pool if not q.get("reveal")]
    picked = random.sample(eligible, min(count, len(eligible))) if eligible else []
    return {"ok": True, "mode": "ffa", "questions": picked, "status": scoring.get_ffa_status()}


@app.post("/api/ffa/submit")
async def api_ffa_submit(request: Request, user: Dict[str, Any] = Depends(require_user)):
    user_id = user["user_id"]
    if user.get("role") == "trial" or user_id == 0:
        raise HTTPException(status_code=403, detail="Pro účast ve Free For All aréně je nutné se přihlásit.")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")
    user_db = db.get_user_by_id(user_id)
    username = user_db["username"] if user_db else user.get("username", "Student")
    correct_count, total_q, time_ms, explicit_score, _ = _evaluate_competitive_submission(user_id, payload)
    return scoring.submit_ffa_run(
        user_id=user_id,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms,
        explicit_score=explicit_score
    )


@app.get("/api/duel/status")
def api_duel_status(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_duel_status(user.get("user_id") or 0)


@app.post("/api/duel/start")
async def api_duel_start(request: Request, user: Dict[str, Any] = Depends(require_user)):
    import random
    uid = user.get("user_id") or 0
    count = scoring.KOTH_DEFAULT_QUESTIONS
    source = ""
    duel_id = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            count = max(1, min(30, int(body.get("count", count))))
            source = str(body.get("source", ""))
            duel_id = body.get("duel_id")
    except Exception:
        pass

    conn = db.get_db()
    open_row = None
    if duel_id is not None:
        open_row = conn.execute("SELECT * FROM duel_matches WHERE id = ? AND status = 'open'", (int(duel_id),)).fetchone()
    if open_row is None and uid > 0:
        open_row = conn.execute("SELECT * FROM duel_matches WHERE status = 'open' AND creator_id != ? ORDER BY id ASC LIMIT 1", (uid,)).fetchone()

    picked = []
    matched_duel = None
    if open_row is not None and open_row["creator_id"] != uid:
        try:
            q_ids = json.loads(open_row["question_ids_json"] or "[]")
            picked = [ALL_QUESTIONS[str(qid)] for qid in q_ids if str(qid) in ALL_QUESTIONS]
        except Exception:
            picked = []
        matched_duel = {
            "id": open_row["id"],
            "creator_username": open_row["creator_username"],
            "creator_score": open_row["creator_score"]
        }

    if not picked:
        try:
            pool = tzi_trener.load_questions(source or tzi_trener.ALL)
        except Exception:
            pool = list(ALL_QUESTIONS.values())
        eligible = [q for q in pool if not q.get("reveal")]
        picked = random.sample(eligible, min(count, len(eligible))) if eligible else []

    return {
        "ok": True,
        "mode": "duel",
        "duel": matched_duel,
        "questions": picked,
        "status": scoring.get_duel_status(uid)
    }


@app.post("/api/duel/submit")
async def api_duel_submit(request: Request, user: Dict[str, Any] = Depends(require_user)):
    user_id = user["user_id"]
    if user.get("role") == "trial" or user_id == 0:
        raise HTTPException(status_code=403, detail="Pro 1v1 souboj je nutné se přihlásit.")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")
    user_db = db.get_user_by_id(user_id)
    username = user_db["username"] if user_db else user.get("username", "Student")
    correct_count, total_q, time_ms, explicit_score, q_ids = _evaluate_competitive_submission(user_id, payload)
    duel_id = payload.get("duel_id")
    return scoring.submit_duel_match(
        user_id=user_id,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms,
        question_ids=q_ids,
        duel_id=int(duel_id) if duel_id is not None else None,
        explicit_score=explicit_score
    )


@app.post("/webhook")
def post_webhook(request: Request, secret: str = ""):
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    out = git_pull()
    return PlainTextResponse(f"OK: {out}")


# --- Main Frontend View ---
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    try:
        content = tzi_trener.load_ui("novy")
    except OSError:
        return PlainTextResponse("Chybí soubor šablony UI.", status_code=500)

    return HTMLResponse(content)


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
