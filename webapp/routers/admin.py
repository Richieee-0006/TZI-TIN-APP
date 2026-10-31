"""Admin panel: přehled uživatelů."""
from html import escape
from typing import Dict, Any
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
import db
import scoring
from ..pages import ADMIN_HTML
from ..sessions import require_admin

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request, limit: int = 100, user: Dict[str, Any] = Depends(require_admin)):
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

    fetch_limit = max(1, min(1000, limit)) if limit > 0 else 500
    error_logs = db.get_recent_errors(fetch_limit)
    error_rows = ""
    levels_set = set()
    endpoints_set = set()
    for err in error_logs:
        lvl = str(err.get("level") or "UNKNOWN")
        levels_set.add(lvl)
        lvl_color = "var(--red)" if lvl in ("ERROR", "UI_ERROR") else ("var(--yellow)" if lvl == "WARNING" else "var(--peach)")
        lvl_badge = f'<span class="badge" style="background:rgba(243,139,168,0.2);color:{lvl_color}">{escape(lvl)}</span>'
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
    html = html.replace("<!--USERS_ROWS-->", rows if rows else "<tr><td colspan='7'>Žádní studenti zatím nejsou registrováni.</td></tr>")
    html = html.replace("<!--ERRORS_ROWS-->", error_rows if error_rows else "<tr><td colspan='5' style='color:var(--text-dim);'>Žádné chyby nezaznamenány.</td></tr>")
    return html
