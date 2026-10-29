"""Asynchronní souboje 1v1."""
from typing import Dict, Any, Optional, List
from db import get_db
from .constants import KOTH_DEFAULT_QUESTIONS


def get_duel_status(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Vrátí otevřené 1v1 výzvy, dokončené souboje 1v1 a žebříček 1v1 vítězství."""
    import json
    conn = get_db()
    open_rows = conn.execute(
        """
        SELECT id, creator_id, creator_username, creator_score, creator_correct, creator_time_ms,
               question_ids_json, created_at
        FROM duel_matches
        WHERE status = 'open'
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    completed_rows = conn.execute(
        """
        SELECT id, creator_id, creator_username, creator_score, creator_correct,
               opponent_id, opponent_username, opponent_score, opponent_correct,
               winner_id, winner_username, completed_at
        FROM duel_matches
        WHERE status = 'completed'
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    win_rows = conn.execute(
        """
        SELECT winner_id AS user_id, winner_username AS username, COUNT(*) AS wins
        FROM duel_matches
        WHERE status = 'completed' AND winner_id IS NOT NULL
        GROUP BY winner_id, winner_username
        ORDER BY wins DESC
        LIMIT 10
        """
    ).fetchall()

    open_challenges = []
    for r in open_rows:
        try:
            q_ids = json.loads(r["question_ids_json"] or "[]")
        except Exception:
            q_ids = []
        open_challenges.append({
            "id": r["id"],
            "creator_id": r["creator_id"],
            "creator_username": r["creator_username"],
            "creator_score": r["creator_score"],
            "creator_correct": r["creator_correct"],
            "question_count": len(q_ids) or KOTH_DEFAULT_QUESTIONS,
            "created_at": r["created_at"]
        })

    return {
        "open_challenges": open_challenges,
        "recent_duels": [dict(r) for r in completed_rows],
        "leaderboard": [dict(r) for r in win_rows]
    }


def submit_duel_match(
    user_id: int,
    username: str,
    correct_count: int,
    total_questions: int,
    time_ms: int = 0,
    question_ids: Optional[List[str]] = None,
    duel_id: Optional[int] = None,
    explicit_score: Optional[int] = None
) -> Dict[str, Any]:
    """Vyhodnotí 1v1 souboj: buď dokončí otevřenou výzvu soupeře, nebo založí novou 1v1 výzvu."""
    import json
    conn = get_db()
    time_ms_clean = max(0, int(time_ms or 0))
    correct_clean = max(0, int(correct_count or 0))
    total_clean = max(1, int(total_questions or KOTH_DEFAULT_QUESTIONS))

    if explicit_score is not None:
        score = max(0, int(explicit_score))
    else:
        speed_bonus = max(0, 120 - (time_ms_clean // 1000)) if correct_clean > 0 else 0
        score = correct_clean * 100 + speed_bonus

    with conn:
        target_row = None
        if duel_id is not None:
            target_row = conn.execute(
                "SELECT * FROM duel_matches WHERE id = ? AND status = 'open'",
                (int(duel_id),)
            ).fetchone()
        if target_row is None:
            target_row = conn.execute(
                "SELECT * FROM duel_matches WHERE status = 'open' AND creator_id != ? ORDER BY id ASC LIMIT 1",
                (user_id,)
            ).fetchone()

        if target_row is not None and target_row["creator_id"] != user_id:
            d_id = target_row["id"]
            c_id = target_row["creator_id"]
            c_name = target_row["creator_username"]
            c_score = target_row["creator_score"]
            c_time = target_row["creator_time_ms"]

            if score > c_score or (score == c_score and time_ms_clean < c_time):
                winner_id = user_id
                winner_name = username
            elif c_score > score or (c_score == score and c_time < time_ms_clean):
                winner_id = c_id
                winner_name = c_name
            else:
                winner_id = None
                winner_name = None

            conn.execute(
                """
                UPDATE duel_matches
                SET opponent_id = ?, opponent_username = ?, opponent_score = ?,
                    opponent_correct = ?, opponent_time_ms = ?, status = 'completed',
                    winner_id = ?, winner_username = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user_id, username, score, correct_clean, time_ms_clean, winner_id, winner_name, d_id)
            )
            st = get_duel_status(user_id)
            return {
                "ok": True,
                "mode": "duel",
                "resolved": True,
                "duel_id": d_id,
                "won_duel": winner_id == user_id,
                "tied": winner_id is None,
                "winner_username": winner_name,
                "my_score": score,
                "opponent_username": c_name,
                "opponent_score": c_score,
                "correct_count": correct_clean,
                "total_questions": total_clean,
                "time_ms": time_ms_clean,
                "status": st
            }
        else:
            cursor = conn.execute(
                """
                INSERT INTO duel_matches (
                    creator_id, creator_username, creator_score, creator_correct,
                    creator_time_ms, question_ids_json, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open')
                """,
                (
                    user_id,
                    username,
                    score,
                    correct_clean,
                    time_ms_clean,
                    json.dumps(question_ids or [])
                )
            )
            new_id = cursor.lastrowid
            st = get_duel_status(user_id)
            return {
                "ok": True,
                "mode": "duel",
                "resolved": False,
                "duel_id": new_id,
                "won_duel": None,
                "tied": False,
                "my_score": score,
                "correct_count": correct_clean,
                "total_questions": total_clean,
                "time_ms": time_ms_clean,
                "status": st
            }
