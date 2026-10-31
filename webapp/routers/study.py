"""Studijní API: profil, otázky, postup a synchronizace offline fronty."""
import json
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
import db
import scoring
import tzi_trener
from .. import questions
from ..questions import verify_answer
from ..sessions import require_user

router = APIRouter()


# --- API Endpoints ---
@router.get("/api/me")
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


@router.get("/api/daily-progress")
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


@router.get("/api/sources")
def api_sources(user: Dict[str, Any] = Depends(require_user)):
    srcs = tzi_trener.list_sources()
    real = [s for s in srcs if s["id"] != tzi_trener.ALL]
    default = real[-1]["id"] if real else ""
    return {"sources": srcs, "default": default}


@router.get("/api/questions")
def api_questions(source: str = "", user: Dict[str, Any] = Depends(require_user)):
    try:
        return tzi_trener.load_questions(source)
    except (KeyError, OSError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/recall")
def api_recall(user: Dict[str, Any] = Depends(require_user)):
    try:
        return tzi_trener.load_recall()
    except (KeyError, OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/progress")
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


@router.post("/api/progress")
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
        q = questions.ALL_QUESTIONS.get(q_id)
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


@router.post("/api/sync")
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

        q = questions.ALL_QUESTIONS.get(q_id)
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


@router.post("/api/client-error")
async def api_client_error(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    msg = str(body.get("message", "Unknown error"))[:500]
    ep = str(body.get("file", ""))[:200]
    stack = str(body.get("stack", ""))[:2000]
    db.log_error("UI_ERROR", msg, endpoint=ep, stack_trace=stack)
    return {"ok": True}
