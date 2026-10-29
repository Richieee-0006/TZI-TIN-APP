"""Denní minimální cíl a denní streak."""
from datetime import date, timedelta
from typing import Dict, Any, Optional
from db import get_db
from .constants import DAILY_MIN_GOAL


def get_daily_progress(user_id: int, today_str: Optional[str] = None) -> Dict[str, Any]:
    """Vrátí denní pokrok uživatele, stav denního cíle, kalendářní streak a historii posledních 7 dnů."""
    conn = get_db()
    today_s = today_str or date.today().isoformat()
    today_obj = date.fromisoformat(today_s)
    yesterday_s = (today_obj - timedelta(days=1)).isoformat()

    score_row = conn.execute(
        "SELECT daily_streak, best_daily_streak, last_goal_date FROM user_scores WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    daily_streak = score_row["daily_streak"] if score_row else 0
    best_daily_streak = score_row["best_daily_streak"] if score_row else 0
    last_goal_date = score_row["last_goal_date"] if score_row else None

    if last_goal_date and last_goal_date < yesterday_s and daily_streak != 0:
        daily_streak = 0
        with conn:
            conn.execute(
                "UPDATE user_scores SET daily_streak = 0 WHERE user_id = ?",
                (user_id,)
            )

    dp_row = conn.execute(
        "SELECT questions_answered, questions_correct, goal_met FROM daily_progress WHERE user_id = ? AND activity_date = ?",
        (user_id, today_s)
    ).fetchone()

    q_answered = dp_row["questions_answered"] if dp_row else 0
    q_correct = dp_row["questions_correct"] if dp_row else 0
    goal_met = bool(dp_row["goal_met"]) if dp_row else False

    history_rows = conn.execute(
        """
        SELECT activity_date, questions_answered, questions_correct, goal_met
        FROM daily_progress
        WHERE user_id = ?
        ORDER BY activity_date DESC
        LIMIT 7
        """,
        (user_id,)
    ).fetchall()

    return {
        "date": today_s,
        "questions_answered": q_answered,
        "questions_correct": q_correct,
        "daily_goal": DAILY_MIN_GOAL,
        "goal_met": goal_met,
        "daily_streak": daily_streak,
        "best_daily_streak": best_daily_streak,
        "last_goal_date": last_goal_date,
        "history": [
            {
                "date": r["activity_date"],
                "questions_answered": r["questions_answered"],
                "questions_correct": r["questions_correct"],
                "goal_met": bool(r["goal_met"])
            }
            for r in history_rows
        ]
    }
