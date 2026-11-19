"""Admin panel: přehled uživatelů a správa žebříčku."""
from html import escape
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Response, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import db
import scoring
from ..pages import ADMIN_HTML
from ..sessions import require_admin
from ..csrf import ensure_csrf_token, validate_csrf

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request, response: Response, limit: int = 100, user: Dict[str, Any] = Depends(require_admin)):
    csrf_tok = ensure_csrf_token(request, response)
    students = scoring.get_admin_leaderboard()
    rows = ""
    for idx, s in enumerate(students, 1):
        role_badge = f'<span class="badge badge-{escape(str(s["role"]))}">{escape(str(s["role"]))}</span>'
        hidden = bool(s.get("hide_leaderboard", 0))
        status_badge = '<span class="badge badge-hidden">Skryt</span>' if hidden else ''

        if s.get("role") == "admin":
            action_html = '<span class="adm-dash">-</span>'
        else:
            u_name = escape(str(s.get("username", "")))
            uid = int(s["id"])
            pts = int(s.get("total_points") or 0)
            stk = int(s.get("current_streak") or 0)
            action_verb = "vrátit do" if hidden else "odebrat z"
            toggle_text = "Vrátit do žebříčku" if hidden else "Odebrat z žebříčku"
            btn_class = "btn-action-success" if hidden else "btn-action-danger"
            confirm_toggle = f"Opravdu chcete studenta {u_name} {action_verb} veřejného žebříčku?"
            action_html = f"""
            <div class="adm-actions">
                <form method="POST" action="/admin/leaderboard/toggle" class="adm-inline-form" data-confirm="{confirm_toggle}">
                    <input type="hidden" name="user_id" value="{uid}">
                    <input type="hidden" name="csrf_token" value="{csrf_tok}">
                    <button type="submit" class="btn-action {btn_class}">
                        {toggle_text}
                    </button>
                </form>
                <button type="button" class="btn-action btn-action-warning" data-reset-modal data-uid="{uid}" data-username="{u_name}" data-points="{pts}" data-streak="{stk}">
                    Vynulovat
                </button>
            </div>
            """

        rows += f"""
        <tr class="student-row" data-username="{escape(str(s['username']))}">
            <td><b>#{idx}</b></td>
            <td><b>{escape(str(s['username']))}</b>{status_badge}</td>
            <td>{escape(str(s.get('theme', 'games')))}</td>
            <td><b class="adm-pts">{s.get('total_points') or 0} b.</b></td>
            <td>{s.get('current_streak') or 0}</td>
            <td>{s.get('best_streak') or 0}</td>
            <td>{role_badge}</td>
            <td class="adm-nowrap">{action_html}</td>
        </tr>
        """

    fetch_limit = max(1, min(1000, limit)) if limit > 0 else 500
    error_logs = db.get_recent_errors(fetch_limit)
    error_rows = ""
    levels_set = set()
    endpoints_set = set()
    for err in error_logs:
        lvl = str(err.get("level") or "UNKNOWN")
        levels_set.add(lvl)
        if lvl in ("ERROR", "UI_ERROR"):
            lvl_cls = "badge-err"
        elif lvl == "WARNING":
            lvl_cls = "badge-warn"
        else:
            lvl_cls = "badge-info"
        lvl_badge = f'<span class="badge {lvl_cls}">{escape(lvl)}</span>'
        ts = escape(str(err.get("created_at") or "")[:19].replace("T", " "))
        ep = str(err.get("endpoint") or "-")
        if ep and ep != "-":
            endpoints_set.add(ep)
        uid = str(err.get("user_id") if err.get("user_id") is not None else "-")
        msg = escape(str(err.get("message") or ""))
        stack = escape(str(err.get("stack_trace") or ""))
        stack_html = f'<br><details class="adm-stack"><summary>Stacktrace</summary><pre>{stack}</pre></details>' if stack else ""

        error_rows += f"""
        <tr class="error-item" data-level="{escape(lvl)}" data-endpoint="{escape(ep)}" data-uid="{escape(uid)}" data-ts="{escape(ts)}">
            <td class="adm-ts">{ts}</td>
            <td>{lvl_badge}</td>
            <td class="adm-ep" title="{escape(ep)}">{escape(ep)}</td>
            <td><code>{escape(uid)}</code></td>
            <td class="msg-col adm-msg-col">{msg}{stack_html}</td>
        </tr>
        """

    html = ADMIN_HTML.replace("<!--GENERATED_CODE_SECTION-->", "")
    html = html.replace("<!--CURRENT_LIMIT-->", str(fetch_limit))
    html = html.replace("<!--CSRF_TOKEN-->", csrf_tok)
    html = html.replace("<!--USERS_ROWS-->", rows if rows else "<tr><td colspan='8'>Žádní studenti zatím nejsou registrováni.</td></tr>")
    html = html.replace("<!--ERRORS_ROWS-->", error_rows if error_rows else "<tr><td colspan='5' class='adm-empty'>Žádné chyby nezaznamenány.</td></tr>")
    return html


@router.post("/admin/leaderboard/toggle")
async def post_admin_leaderboard_toggle(
    request: Request,
    response: Response,
    user_id: int = Form(...),
    csrf_token: Optional[str] = Form(None),
    admin: Dict[str, Any] = Depends(require_admin),
):
    await validate_csrf(request, response, csrf_token=csrf_token)
    if user_id < 1 or user_id > 9223372036854775807:
        raise HTTPException(status_code=400, detail="Neplatné user_id.")
    db.toggle_user_leaderboard_visibility(user_id)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/leaderboard/reset")
async def post_admin_leaderboard_reset(
    request: Request,
    response: Response,
    user_id: int = Form(...),
    scope: str = Form("all"),
    csrf_token: Optional[str] = Form(None),
    admin: Dict[str, Any] = Depends(require_admin),
):
    await validate_csrf(request, response, csrf_token=csrf_token)
    if user_id < 1 or user_id > 9223372036854775807:
        raise HTTPException(status_code=400, detail="Neplatné user_id.")
    allowed_scopes = {"all", "points", "streaks", "arena"}
    clean_scope = scope if scope in allowed_scopes else "all"
    db.reset_user_score(user_id, scope=clean_scope)
    return RedirectResponse(url="/admin", status_code=303)
