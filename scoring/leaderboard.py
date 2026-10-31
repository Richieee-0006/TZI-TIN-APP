"""Žebříček uživatelů (veřejný i admin)."""
from typing import Dict, Any, Optional
from db import get_db
from .daily import get_daily_progress


def get_user_leaderboard_position(user_id: int, today_str: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    user_row = conn.execute(
        """
        SELECT s.total_points, s.current_streak, s.best_streak, COALESCE(u.hide_leaderboard, 0) as hide_leaderboard
        FROM users u
        LEFT JOIN user_scores s ON u.id = s.user_id
        WHERE u.id = ?
        """,
        (user_id,)
    ).fetchone()

    points = user_row["total_points"] if user_row and user_row["total_points"] else 0
    streak = user_row["current_streak"] if user_row and user_row["current_streak"] else 0
    best_streak = user_row["best_streak"] if user_row and user_row["best_streak"] else 0
    is_hidden = bool(user_row and user_row["hide_leaderboard"])

    dp = get_daily_progress(user_id, today_str=today_str)

    if is_hidden:
        rank = "-"
    else:
        # Počet aktivních viditelných uživatelů s více body
        rank_row = conn.execute(
            """
            SELECT COUNT(*) AS better_count
            FROM users u
            JOIN user_scores s ON u.id = s.user_id
            WHERE COALESCE(u.hide_leaderboard, 0) = 0 AND u.role != 'admin' AND s.total_points > ?
            """,
            (points,)
        ).fetchone()
        rank = (rank_row["better_count"] if rank_row else 0) + 1

    total_row = conn.execute(
        "SELECT COUNT(*) AS total_count FROM users WHERE COALESCE(hide_leaderboard, 0) = 0 AND role != 'admin'"
    ).fetchone()
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


def get_public_leaderboard(limit: int = 30) -> list:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT u.id, u.username, u.theme, u.role, s.total_points, s.current_streak, s.best_streak,
               s.daily_streak, s.best_daily_streak, s.last_active
        FROM users u
        LEFT JOIN user_scores s ON u.id = s.user_id
        WHERE COALESCE(u.hide_leaderboard, 0) = 0 AND u.role != 'admin'
        ORDER BY COALESCE(s.total_points, 0) DESC, s.best_streak DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_admin_leaderboard() -> list:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT u.id, u.username, u.theme, u.role, COALESCE(u.hide_leaderboard, 0) AS hide_leaderboard,
               s.total_points, s.current_streak, s.best_streak,
               s.daily_streak, s.best_daily_streak, s.last_active
        FROM users u
        LEFT JOIN user_scores s ON u.id = s.user_id
        ORDER BY COALESCE(s.total_points, 0) DESC, s.best_streak DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]
