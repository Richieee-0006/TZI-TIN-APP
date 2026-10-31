"""Soutěžní režimy: King of the Hill, FFA, 1v1 duel a místnosti (lobby)."""
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
import db
import scoring
import tzi_trener
from .. import questions
from ..questions import verify_answer
from ..sessions import require_user

router = APIRouter()


# --- King of the Hill (FFA / 1v1) Endpoints ---
@router.get("/api/koth/status")
def api_koth_status(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_koth_status()


@router.get("/api/koth/leaderboard")
def api_koth_leaderboard(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_koth_status()


@router.post("/api/koth/start")
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
        pool = list(questions.ALL_QUESTIONS.values())

    eligible = [q for q in pool if not q.get("reveal")]
    picked = random.sample(eligible, min(count, len(eligible))) if eligible else []
    status = scoring.get_koth_status()
    return {
        "ok": True,
        "questions": picked,
        "king": status["king"],
        "status": status
    }


@router.post("/api/koth/submit")
async def api_koth_submit(request: Request, user: Dict[str, Any] = Depends(require_user)):
    user_id = user["user_id"]
    if user.get("role") == "trial" or user_id == 0:
        raise HTTPException(status_code=403, detail="Pro souboj o Krále kopce je nutné se přihlásit.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")

    answers = payload.get("answers")
    if not isinstance(answers, list) or len(answers) == 0:
        raise HTTPException(status_code=400, detail="Pole answers je povinné.")

    try:
        raw_time = payload.get("time_ms", 0)
        time_ms = max(0, int(0 if raw_time is None else raw_time))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Neplatný čas (time_ms).")

    user_db = db.get_user_by_id(user_id)
    username = user_db["username"] if user_db else user.get("username", "Student")

    correct_count = 0
    total_q = len(answers)

    for item in answers:
        if not isinstance(item, dict):
            continue
        q_id = str(item.get("id", ""))
        q = questions.ALL_QUESTIONS.get(q_id)
        u_ans = item.get("userKeys") if item.get("userKeys") is not None else item.get("user_answer")
        if q and u_ans is not None:
            is_ok = verify_answer(q, u_ans)
        else:
            is_ok = False
        if is_ok:
            correct_count += 1
        if q_id:
            scoring.record_question_answer(user_id, q_id, is_ok)

    return scoring.submit_koth_challenge(
        user_id=user_id,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms
    )


def _evaluate_competitive_submission(user_id: int, payload: Dict[str, Any]):
    answers = payload.get("answers")
    if not isinstance(answers, list) or len(answers) == 0:
        raise HTTPException(status_code=400, detail="Pole answers je povinné.")

    try:
        raw_time = payload.get("time_ms", 0)
        time_ms = max(0, int(0 if raw_time is None else raw_time))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Neplatný čas (time_ms).")

    correct_count = 0
    total_q = len(answers)
    question_ids = []

    for item in answers:
        if not isinstance(item, dict):
            continue
        q_id = str(item.get("id", ""))
        if q_id:
            question_ids.append(q_id)
        q = questions.ALL_QUESTIONS.get(q_id)
        u_ans = item.get("userKeys") if item.get("userKeys") is not None else item.get("user_answer")
        if q and u_ans is not None:
            is_ok = verify_answer(q, u_ans)
        else:
            is_ok = False
        if is_ok:
            correct_count += 1
        if q_id:
            scoring.record_question_answer(user_id, q_id, is_ok)

    return correct_count, total_q, time_ms, question_ids


@router.get("/api/competitive/overview")
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
    picked = [questions.ALL_QUESTIONS[str(qid)] for qid in q_ids if str(qid) in questions.ALL_QUESTIONS]
    if not picked:
        import random
        src = room.get("source") or ""
        cnt = int(room.get("question_count") or scoring.KOTH_DEFAULT_QUESTIONS)
        try:
            pool = tzi_trener.load_questions(src or tzi_trener.ALL)
        except Exception:
            pool = list(questions.ALL_QUESTIONS.values())
        eligible = [q for q in pool if not q.get("reveal")]
        picked = random.sample(eligible, min(cnt, len(eligible))) if eligible else []
    return picked


@router.get("/api/rooms")
def api_rooms_list(user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    return scoring.list_comp_rooms(uid)


@router.post("/api/rooms/create")
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
        pool = list(questions.ALL_QUESTIONS.values())
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


@router.get("/api/rooms/{room_id}")
def api_room_detail(room_id: int, user: Dict[str, Any] = Depends(require_user)):
    room = scoring.get_comp_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Místnost neexistuje.")
    questions = _resolve_room_questions(room) if room.get("status") in ("in_progress", "completed") else []
    return {"ok": True, "room": room, "questions": questions}


@router.post("/api/rooms/{room_id}/join")
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


@router.post("/api/rooms/{room_id}/start")
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


@router.post("/api/rooms/{room_id}/leave")
def api_room_leave(room_id: int, user: Dict[str, Any] = Depends(require_user)):
    uid = user.get("user_id") or 0
    return scoring.leave_comp_room(room_id, uid)


@router.post("/api/rooms/{room_id}/submit")
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
    correct_count, total_q, time_ms, _ = _evaluate_competitive_submission(uid, payload)
    res = scoring.submit_comp_room_result(
        room_id=room_id,
        user_id=uid,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms,
    )
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "Místnost neexistuje."))
    return res


@router.get("/api/ffa/status")
def api_ffa_status(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_ffa_status()


@router.post("/api/ffa/start")
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
        pool = list(questions.ALL_QUESTIONS.values())
    eligible = [q for q in pool if not q.get("reveal")]
    picked = random.sample(eligible, min(count, len(eligible))) if eligible else []
    return {"ok": True, "mode": "ffa", "questions": picked, "status": scoring.get_ffa_status()}


@router.post("/api/ffa/submit")
async def api_ffa_submit(request: Request, user: Dict[str, Any] = Depends(require_user)):
    user_id = user["user_id"]
    if user.get("role") == "trial" or user_id == 0:
        raise HTTPException(status_code=403, detail="Pro účast ve Free For All aréně je nutné se přihlásit.")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neplatný JSON")

    try:
        raw_time = payload.get("time_ms", 0)
        time_ms = int(0 if raw_time is None else raw_time)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Neplatný čas (time_ms).")
    if time_ms < 5000:
        raise HTTPException(status_code=400, detail="Čas dokončení je příliš krátký (minimálně 5 sekund).")

    answers = payload.get("answers")
    if not isinstance(answers, list) or len(answers) == 0:
        raise HTTPException(status_code=400, detail="Pole answers je povinné.")

    user_db = db.get_user_by_id(user_id)
    username = user_db["username"] if user_db else user.get("username", "Student")

    correct_count = 0
    total_q = len(answers)
    for item in answers:
        if not isinstance(item, dict):
            continue
        q_id = str(item.get("id", ""))
        q = questions.ALL_QUESTIONS.get(q_id)
        u_ans = item.get("userKeys") if item.get("userKeys") is not None else item.get("user_answer")
        if q and u_ans is not None:
            is_ok = verify_answer(q, u_ans)
        else:
            is_ok = False
        if is_ok:
            correct_count += 1
        if q_id:
            scoring.record_question_answer(user_id, q_id, is_ok)

    return scoring.submit_ffa_run(
        user_id=user_id,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms
    )


@router.get("/api/duel/status")
def api_duel_status(user: Dict[str, Any] = Depends(require_user)):
    return scoring.get_duel_status(user.get("user_id") or 0)


@router.post("/api/duel/start")
async def api_duel_start(request: Request, user: Dict[str, Any] = Depends(require_user)):
    import random
    uid = user.get("user_id") or 0
    count = scoring.KOTH_DEFAULT_QUESTIONS
    source = ""
    duel_id = None
    opponent_id = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            count = max(1, min(30, int(body.get("count", count))))
            source = str(body.get("source", ""))
            duel_id = body.get("duel_id")
            opponent_id = body.get("opponent_id")
    except Exception:
        pass

    if opponent_id is not None:
        try:
            opponent_id_val = int(opponent_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Neplatné opponent_id.")
        if opponent_id_val == uid:
            raise HTTPException(status_code=400, detail="Nelze vyzvat sám sebe.")

    conn = db.get_db()
    open_row = None
    if duel_id is not None:
        try:
            duel_id_val = int(duel_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Neplatné duel_id.")
        open_row = conn.execute("SELECT * FROM duel_matches WHERE id = ? AND status = 'open'", (duel_id_val,)).fetchone()
        if open_row is not None and open_row["creator_id"] == uid:
            raise HTTPException(status_code=400, detail="Nelze vyzvat sám sebe.")
    if open_row is None and uid > 0:
        open_row = conn.execute("SELECT * FROM duel_matches WHERE status = 'open' AND creator_id != ? ORDER BY id ASC LIMIT 1", (uid,)).fetchone()

    picked = []
    matched_duel = None
    if open_row is not None and open_row["creator_id"] != uid:
        try:
            q_ids = json.loads(open_row["question_ids_json"] or "[]")
            picked = [questions.ALL_QUESTIONS[str(qid)] for qid in q_ids if str(qid) in questions.ALL_QUESTIONS]
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
            pool = list(questions.ALL_QUESTIONS.values())
        eligible = [q for q in pool if not q.get("reveal")]
        picked = random.sample(eligible, min(count, len(eligible))) if eligible else []

    return {
        "ok": True,
        "mode": "duel",
        "duel": matched_duel,
        "questions": picked,
        "status": scoring.get_duel_status(uid)
    }


@router.post("/api/duel/submit")
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
    correct_count, total_q, time_ms, q_ids = _evaluate_competitive_submission(user_id, payload)
    duel_id = payload.get("duel_id")
    duel_id_val = None
    if duel_id is not None:
        try:
            duel_id_val = int(duel_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Neplatné duel_id.")
    return scoring.submit_duel_match(
        user_id=user_id,
        username=username,
        correct_count=correct_count,
        total_questions=total_q,
        time_ms=time_ms,
        question_ids=q_ids,
        duel_id=duel_id_val,
    )
