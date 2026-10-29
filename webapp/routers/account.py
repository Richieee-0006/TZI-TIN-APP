"""Účet: žebříček, recap, změna jména/hesla, mazání dat a profilu."""
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import db
import scoring
import tzi_trener
from ..config import SESSION_COOKIE
from ..sessions import create_session_token, require_user

router = APIRouter()


@router.get("/api/leaderboard")
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


@router.get("/api/account/recap")
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


@router.post("/api/account/username")
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
    resp.set_cookie(SESSION_COOKIE, token, max_age=86400 * 30, httponly=True, samesite="lax", secure=True)
    return resp


@router.post("/api/account/password")
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


@router.post("/api/account/revalidate-delete")
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


@router.post("/api/account/delete-profile")
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
