"""Admin panel: přehled uživatelů a pozvánkové kódy."""
from html import escape
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
import db
import scoring
from ..pages import ADMIN_HTML
from ..sessions import require_admin

router = APIRouter()


# --- Admin Panel Endpoints ---
@router.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request, user: Dict[str, Any] = Depends(require_admin), new_code: Optional[str] = None):
    code_section = ""
    if new_code:
        code_section = f"""
        <div class="card" style="border-color:var(--green);">
            <h2 style="color:var(--green);">🎉 Nový kód vygenerován!</h2>
            <p>Zkopíruj tento kód a předej ho spolužákovi k jednorázové registraci:</p>
            <div class="code-box">{escape(new_code)}</div>
            <p style="font-size:0.85rem; color:var(--text-dim);">Kód je v databázi bezpečně zahashován a po použití automaticky zanikne.</p>
        </div>
        """

    students = scoring.get_admin_leaderboard()
    rows = ""
    for idx, s in enumerate(students, 1):
        role_badge = f'<span class="badge badge-{escape(str(s["role"]))}">{escape(str(s["role"]))}</span>'
        rows += f"""
        <tr>
            <td><b>#{idx}</b></td>
            <td><b>{escape(str(s['username']))}</b></td>
            <td>{escape(str(s.get('theme', 'games')))}</td>
            <td><b style="color:var(--mauve);">{s.get('total_points') or 0} b.</b></td>
            <td>🔥 {s.get('current_streak') or 0}</td>
            <td>⭐ {s.get('best_streak') or 0}</td>
            <td>{role_badge}</td>
        </tr>
        """

    error_logs = db.get_recent_errors(30)
    error_rows = ""
    for err in error_logs:
        lvl_color = "var(--red)" if err.get("level") in ("ERROR", "UI_ERROR") else "var(--peach)"
        lvl_badge = f'<span class="badge" style="background:rgba(243,139,168,0.2);color:{lvl_color}">{escape(str(err.get("level")))}</span>'
        ts = escape(str(err.get("created_at") or "")[:19].replace("T", " "))
        ep = escape(str(err.get("endpoint") or "-"))
        uid = escape(str(err.get("user_id") if err.get("user_id") is not None else "-"))
        msg = escape(str(err.get("message") or ""))
        stack = escape(str(err.get("stack_trace") or ""))
        stack_html = f'<br><details style="font-size:0.75rem;color:var(--text-dim);margin-top:4px;"><summary>Stacktrace</summary><pre style="white-space:pre-wrap;margin:4px 0;">{stack}</pre></details>' if stack else ""

        error_rows += f"""
        <tr>
            <td style="font-size:0.85rem;color:var(--text-dim);">{ts}</td>
            <td>{lvl_badge}</td>
            <td style="font-size:0.85rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;">{ep}</td>
            <td>{uid}</td>
            <td style="white-space:normal;max-width:350px;">{msg}{stack_html}</td>
        </tr>
        """

    html = ADMIN_HTML.replace("<!--GENERATED_CODE_SECTION-->", code_section)
    html = html.replace("<!--USERS_ROWS-->", rows if rows else "<tr><td colspan='7'>Žádní studenti zatím nejsou registrováni.</td></tr>")
    html = html.replace("<!--ERRORS_ROWS-->", error_rows if error_rows else "<tr><td colspan='5' style='color:var(--text-dim);'>Žádné chyby nezaznamenány.</td></tr>")
    return html


@router.post("/admin/invite")
def post_admin_invite(user: Dict[str, Any] = Depends(require_admin)):
    code = db.create_invite_code()
    return RedirectResponse(url=f"/admin?new_code={code}", status_code=303)
