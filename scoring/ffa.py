"""Free For All: jednotlivé běhy a vedoucí hráč."""
from typing import Dict, Any, Optional
from db import get_db
from .constants import KOTH_DEFAULT_QUESTIONS


def get_ffa_status() -> Dict[str, Any]:
    """Vrátí stav a žebříček pro kompetitivní režim Free For All (FFA)."""
    conn = get_db()
    lb_rows = conn.execute(
        """
        SELECT user_id, username,
               MAX(score) AS best_score,
               MAX(correct_count) AS best_correct,
               MIN(time_ms) AS best_time_ms,
               COUNT(*) AS runs_count
        FROM ffa_runs
        GROUP BY user_id, username
        ORDER BY best_score DESC, best_time_ms ASC
        LIMIT 10
        """
    ).fetchall()

    recent_rows = conn.execute(
        """
        SELECT id, user_id, username, score, correct_count, total_questions, time_ms, created_at
        FROM ffa_runs
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    leader = dict(lb_rows[0]) if lb_rows else None
    return {
        "leader": leader,
        "leaderboard": [dict(r) for r in lb_rows],
        "recent_runs": [dict(r) for r in recent_rows],
        "total_players": len(lb_rows)
    }


def submit_ffa_run(
    user_id: int,
    username: str,
    correct_count: int,
    total_questions: int,
    time_ms: int = 0,
    explicit_score: Optional[int] = None
) -> Dict[str, Any]:
    """Zaznamená hru v režimu Free For All (FFA) a vrátí umístění v aréně."""
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
        conn.execute(
            """
            INSERT INTO ffa_runs (user_id, username, score, correct_count, total_questions, time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, score, correct_clean, total_clean, time_ms_clean)
        )

    st = get_ffa_status()
    rank = 1
    for idx, row in enumerate(st["leaderboard"], 1):
        if row["user_id"] == user_id:
            rank = idx
            break

    return {
        "ok": True,
        "mode": "ffa",
        "score": score,
        "correct_count": correct_clean,
        "total_questions": total_clean,
        "time_ms": time_ms_clean,
        "rank": rank,
        "is_leader": st["leader"] is not None and st["leader"]["user_id"] == user_id,
        "status": st
    }
