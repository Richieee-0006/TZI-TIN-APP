"""King of the Hill: trůn, výzvy a obrany."""
from typing import Dict, Any, Optional
from db import get_db
from .constants import KOTH_DEFAULT_QUESTIONS


def get_koth_status() -> Dict[str, Any]:
    """Vrátí aktuálního držitele kopce (King of the Hill), nedávné souboje a žebříček králů."""
    conn = get_db()
    state_row = conn.execute("SELECT * FROM koth_state WHERE id = 1").fetchone()
    king = None
    if state_row and state_row["king_user_id"] is not None:
        king = {
            "user_id": state_row["king_user_id"],
            "username": state_row["king_username"],
            "score": state_row["king_score"],
            "correct": state_row["king_correct"],
            "time_ms": state_row["king_time_ms"],
            "crowned_at": state_row["crowned_at"],
            "defenses_count": state_row["defenses_count"]
        }

    match_rows = conn.execute(
        """
        SELECT id, challenger_id, challenger_username, defender_id, defender_username,
               defender_score_before, challenger_score, correct_count, total_questions,
               time_ms, won_throne, created_at
        FROM koth_matches
        ORDER BY id DESC
        LIMIT 12
        """
    ).fetchall()

    lb_rows = conn.execute(
        """
        SELECT challenger_id AS user_id,
               challenger_username AS username,
               MAX(challenger_score) AS best_score,
               SUM(won_throne) AS crowns_won,
               COUNT(*) AS attempts
        FROM koth_matches
        GROUP BY challenger_id, challenger_username
        ORDER BY crowns_won DESC, best_score DESC
        LIMIT 10
        """
    ).fetchall()

    return {
        "king": king,
        "recent_matches": [
            {
                "id": r["id"],
                "challenger_id": r["challenger_id"],
                "challenger_username": r["challenger_username"],
                "defender_id": r["defender_id"],
                "defender_username": r["defender_username"],
                "defender_score_before": r["defender_score_before"],
                "challenger_score": r["challenger_score"],
                "correct_count": r["correct_count"],
                "total_questions": r["total_questions"],
                "time_ms": r["time_ms"],
                "won_throne": bool(r["won_throne"]),
                "created_at": r["created_at"]
            }
            for r in match_rows
        ],
        "leaderboard": [dict(r) for r in lb_rows]
    }


def submit_koth_challenge(
    user_id: int,
    username: str,
    correct_count: int,
    total_questions: int,
    time_ms: int = 0,
    explicit_score: Optional[int] = None
) -> Dict[str, Any]:
    """Vyhodnotí pokus v King of the Hill 1v1 / FFA a případně dosadí nového krále na trůn."""
    conn = get_db()
    time_ms_clean = max(0, int(time_ms or 0))
    correct_clean = max(0, int(correct_count or 0))
    total_clean = max(1, int(total_questions or KOTH_DEFAULT_QUESTIONS))

    if explicit_score is not None:
        challenger_score = max(0, int(explicit_score))
    else:
        speed_bonus = max(0, 120 - (time_ms_clean // 1000)) if correct_clean > 0 else 0
        challenger_score = correct_clean * 100 + speed_bonus

    with conn:
        state_row = conn.execute("SELECT * FROM koth_state WHERE id = 1").fetchone()
        prev_king_id = state_row["king_user_id"] if state_row else None
        prev_king_username = state_row["king_username"] if state_row else None
        prev_king_score = state_row["king_score"] if state_row else 0
        prev_defenses = state_row["defenses_count"] if state_row else 0

        won_throne = False
        if prev_king_id is None or challenger_score > prev_king_score:
            won_throne = True
            new_defenses = (prev_defenses + 1) if prev_king_id == user_id else 0
            conn.execute(
                """
                INSERT INTO koth_state (id, king_user_id, king_username, king_score, king_correct, king_time_ms, crowned_at, defenses_count)
                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(id) DO UPDATE SET
                    king_user_id = excluded.king_user_id,
                    king_username = excluded.king_username,
                    king_score = excluded.king_score,
                    king_correct = excluded.king_correct,
                    king_time_ms = excluded.king_time_ms,
                    crowned_at = CURRENT_TIMESTAMP,
                    defenses_count = excluded.defenses_count
                """,
                (user_id, username, challenger_score, correct_clean, time_ms_clean, new_defenses)
            )
        else:
            conn.execute(
                "UPDATE koth_state SET defenses_count = defenses_count + 1 WHERE id = 1"
            )

        conn.execute(
            """
            INSERT INTO koth_matches (
                challenger_id, challenger_username, defender_id, defender_username,
                defender_score_before, challenger_score, correct_count, total_questions,
                time_ms, won_throne
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                prev_king_id,
                prev_king_username,
                prev_king_score,
                challenger_score,
                correct_clean,
                total_clean,
                time_ms_clean,
                1 if won_throne else 0
            )
        )

    status = get_koth_status()
    return {
        "ok": True,
        "mode": "koth",
        "won_throne": won_throne,
        "challenger_score": challenger_score,
        "correct_count": correct_clean,
        "total_questions": total_clean,
        "time_ms": time_ms_clean,
        "previous_king_score": prev_king_score,
        "previous_king_username": prev_king_username,
        "king": status["king"],
        "status": status
    }
