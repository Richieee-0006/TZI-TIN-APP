"""Admin panel: přehled uživatelů a správa žebříčku."""
from html import escape
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Response, Form, Depends
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
        status_badge = '<span class="badge" style="background:rgba(243,139,168,0.2);color:var(--red);margin-left:4px;">Skryt</span>' if hidden else ''

        if s.get("role") == "admin":
            action_html = '<span style="color:var(--text-dim);font-size:0.8rem;">-</span>'
        else:
            u_name = escape(str(s.get("username", "")))
            action_verb = "vrátit do" if hidden else "odebrat z"
            toggle_text = "Vrátit do žebříčku" if hidden else "Odebrat z žebříčku"
            toggle_bg = "var(--green)" if hidden else "var(--red)"
            confirm_toggle = f"return confirm('Opravdu chcete studenta {u_name} {action_verb} veřejného žebříčku?');"
            action_html = f"""
            <form method="POST" action="/admin/leaderboard/toggle" style="display:inline;margin:0 4px 0 0;" onsubmit="{confirm_toggle}">
                <input type="hidden" name="user_id" value="{s['id']}">
                <input type="hidden" name="csrf_token" value="{csrf_tok}">
                <button type="submit" class="btn" style="padding:0.25rem 0.55rem;font-size:0.75rem;background:{toggle_bg};color:#11111b;border-radius:0.4rem;">
                    {toggle_text}
                </button>
            </form>
            <form method="POST" action="/admin/leaderboard/reset" style="display:inline-flex;align-items:center;gap:3px;margin:0;" onsubmit="var sel=this.querySelector('select');var txt=sel.options[sel.selectedIndex].text;return confirm('Opravdu chcete studentovi {u_name} ' + txt.toLowerCase() + '?');">
                <input type="hidden" name="user_id" value="{s['id']}">
                <input type="hidden" name="csrf_token" value="{csrf_tok}">
                <select name="scope" style="padding:0.2rem 0.35rem;font-size:0.75rem;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:0.4rem;cursor:pointer;">
                    <option value="all">Všechno (body, streaky, aréna)</option>
                    <option value="points">Pouze body</option>
                    <option value="streaks">Pouze streaky</option>
                    <option value="arena">Pouze arénu</option>
                </select>
                <button type="submit" class="btn" style="padding:0.25rem 0.55rem;font-size:0.75rem;background:var(--yellow);color:#11111b;border-radius:0.4rem;">
                    Vynulovat
                </button>
            </form>
            """

        rows += f"""
        <tr>
            <td><b>#{idx}</b></td>
            <td><b>{escape(str(s['username']))}</b>{status_badge}</td>
            <td>{escape(str(s.get('theme', 'games')))}</td>
            <td><b style="color:var(--mauve);">{s.get('total_points') or 0} b.</b></td>
            <td>🔥 {s.get('current_streak') or 0}</td>
            <td>⭐ {s.get('best_streak') or 0}</td>
            <td>{role_badge}</td>
            <td style="white-space:nowrap;">{action_html}</td>
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
            lvl_color = "var(--red)"
            bg_color = "rgba(243,139,168,0.2)"
        elif lvl == "WARNING":
            lvl_color = "var(--yellow)"
            bg_color = "rgba(249,226,175,0.2)"
        else:
            lvl_color = "var(--green)"
            bg_color = "rgba(166,227,161,0.2)"
        lvl_badge = f'<span class="badge" style="background:{bg_color};color:{lvl_color}">{escape(lvl)}</span>'
        ts = escape(str(err.get("created_at") or "")[:19].replace("T", " "))
        ep = str(err.get("endpoint") or "-")
        if ep and ep != "-":
            endpoints_set.add(ep)
        uid = str(err.get("user_id") if err.get("user_id") is not None else "-")
        msg = escape(str(err.get("message") or ""))
        stack = escape(str(err.get("stack_trace") or ""))
        stack_html = f'<br><details style="font-size:0.75rem;color:var(--text-dim);margin-top:4px;"><summary>Stacktrace</summary><pre style="white-space:pre-wrap;margin:4px 0;background:#11111b;padding:6px;border-radius:4px;">{stack}</pre></details>' if stack else ""

        error_rows += f"""
        <tr class="error-item" data-level="{escape(lvl)}" data-endpoint="{escape(ep)}" data-uid="{escape(uid)}" data-ts="{escape(ts)}">
            <td style="font-size:0.85rem;color:var(--text-dim);white-space:nowrap;">{ts}</td>
            <td>{lvl_badge}</td>
            <td style="font-size:0.85rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;" title="{escape(ep)}">{escape(ep)}</td>
            <td><code>{escape(uid)}</code></td>
            <td class="msg-col" style="white-space:normal;max-width:400px;">{msg}{stack_html}</td>
        </tr>
        """

    html = ADMIN_HTML.replace("<!--GENERATED_CODE_SECTION-->", "")
    html = html.replace("<!--CURRENT_LIMIT-->", str(fetch_limit))
    html = html.replace("<!--USERS_ROWS-->", rows if rows else "<tr><td colspan='8'>Žádní studenti zatím nejsou registrováni.</td></tr>")
    html = html.replace("<!--ERRORS_ROWS-->", error_rows if error_rows else "<tr><td colspan='5' style='color:var(--text-dim);'>Žádné chyby nezaznamenány.</td></tr>")
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
    allowed_scopes = {"all", "points", "streaks", "arena"}
    clean_scope = scope if scope in allowed_scopes else "all"
    db.reset_user_score(user_id, scope=clean_scope)
    return RedirectResponse(url="/admin", status_code=303)
