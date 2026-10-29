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

    html = ADMIN_HTML.replace("<!--GENERATED_CODE_SECTION-->", code_section)
    html = html.replace("<!--USERS_ROWS-->", rows if rows else "<tr><td colspan='7'>Žádní studenti zatím nejsou registrováni.</td></tr>")
    return html


@router.post("/admin/invite")
def post_admin_invite(user: Dict[str, Any] = Depends(require_admin)):
    code = db.create_invite_code()
    return RedirectResponse(url=f"/admin?new_code={code}", status_code=303)
