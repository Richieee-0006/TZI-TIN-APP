"""Žebříček uživatelů (veřejný i admin)."""
from typing import Dict, Any, Optional
from db import get_db
from .daily import get_daily_progress


def get_user_leaderboard_position(user_id: int, today_str: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    user_row = conn.execute(
        "SELECT total_points, current_streak, best_streak FROM user_scores WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    points = user_row["total_points"] if user_row else 0
    streak = user_row["current_streak"] if user_row else 0
    best_streak = user_row["best_streak"] if user_row else 0

    dp = get_daily_progress(user_id, today_str=today_str)

    # Počet uživatelů s více body
    rank_row = conn.execute(
        "SELECT COUNT(*) AS better_count FROM user_scores WHERE total_points > ?",
        (points,)
    ).fetchone()
    rank = (rank_row["better_count"] if rank_row else 0) + 1

    total_row = conn.execute("SELECT COUNT(*) AS total_count FROM user_scores").fetchone()
    total_users = total_row["total_count"] if total_row else 1

    return {
        "rank": rank,
        "total": max(total_users, 1),
        "points": points,
        "current_streak": streak,
        "best_streak": best_streak,
        "daily_streak": dp["daily_streak"],
        "best_daily_streak": dp["best_daily_streak"],
        "daily_goal": dp["daily_goal"],
        "questions_today": dp["questions_answered"],
        "daily_goal_met": dp["goal_met"]
    }


def get_admin_leaderboard() -> list:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT u.id, u.username, u.theme, u.role, s.total_points, s.current_streak, s.best_streak,
               s.daily_streak, s.best_daily_streak, s.last_active
        FROM users u
        LEFT JOIN user_scores s ON u.id = s.user_id
        ORDER BY COALESCE(s.total_points, 0) DESC, s.best_streak DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]
