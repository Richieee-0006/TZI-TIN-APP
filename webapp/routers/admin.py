"""Admin panel: přehled uživatelů."""
from html import escape
from typing import Dict, Any
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
import scoring
from ..pages import ADMIN_HTML
from ..sessions import require_admin

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request, user: Dict[str, Any] = Depends(require_admin)):
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

    html = ADMIN_HTML.replace("<!--GENERATED_CODE_SECTION-->", "")
    html = html.replace("<!--USERS_ROWS-->", rows if rows else "<tr><td colspan='7'>Žádní studenti zatím nejsou registrováni.</td></tr>")
    return html
