"""Bodování odpovědí, obtížnost otázek, streak (record_question_answer)."""
import math
from datetime import date, timedelta
from typing import Dict, Any, Optional, Tuple
from db import get_db
from .constants import DAILY_MIN_GOAL


def is_recall_question(question_id: str) -> bool:
    return question_id.startswith("r-") or "recall" in question_id.lower()


def get_question_difficulty(question_id: str) -> Tuple[float, str, float]:
    conn = get_db()
    row = conn.execute(
        "SELECT total_attempts, correct_attempts FROM question_stats WHERE question_id = ?",
        (question_id,)
    ).fetchone()
    if not row or row["total_attempts"] < 5:
        return 1.0, "normal", 1.0

    total = row["total_attempts"]
    correct = row["correct_attempts"]
    rate = correct / total

    if rate < 0.30:
        return 2.0, "very_hard", rate
    elif rate < 0.50:
        return 1.5, "hard", rate
    else:
        return 1.0, "normal", rate


def record_question_answer(
    user_id: int,
    question_id: str,
    is_correct: bool,
    activity_date: Optional[str] = None
) -> Dict[str, Any]:
    """Zaznamená odpověď studenta, atomicky spočítá body, streak, denní pokrok a aktualizuje statistiky."""
    conn = get_db()
    today_str = activity_date or date.today().isoformat()
    today_obj = date.fromisoformat(today_str)
    yesterday_str = (today_obj - timedelta(days=1)).isoformat()

    with conn:
        # 1. Zjistit číslo pokusu studenta pro tuto otázku
        prev_attempts = conn.execute(
            "SELECT COUNT(*) AS cnt FROM user_answers WHERE user_id = ? AND question_id = ?",
            (user_id, question_id)
        ).fetchone()["cnt"]
        attempt_number = prev_attempts + 1

        # 2. Načíst globální statistiku otázky pro dynamickou obtížnost
        q_row = conn.execute(
            "SELECT total_attempts, correct_attempts FROM question_stats WHERE question_id = ?",
            (question_id,)
        ).fetchone()

        if q_row and q_row["total_attempts"] >= 5:
            rate = q_row["correct_attempts"] / q_row["total_attempts"]
            if rate < 0.30:
                multiplier = 2.0
                difficulty_label = "extra těžká"
            elif rate < 0.50:
                multiplier = 1.5
                difficulty_label = "těžká"
            else:
                multiplier = 1.0
                difficulty_label = "standardní"
        else:
            multiplier = 1.0
            difficulty_label = "standardní"

        # 3. Základní body
        recall = is_recall_question(question_id)
        if is_correct:
            if recall:
                base_points = 5
            else:
                if attempt_number == 1:
                    base_points = 3
                elif attempt_number == 2:
                    base_points = 1
                else:
                    base_points = 0
        else:
            base_points = 0

        # Body po násobiteli obtížnosti
        awarded_points = math.ceil(base_points * multiplier)

        # 4. Načíst stávající streak a denní streak
        score_row = conn.execute(
            """
            SELECT total_points, current_streak, best_streak,
                   daily_streak, best_daily_streak, last_goal_date
            FROM user_scores WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

        current_streak = score_row["current_streak"] if score_row else 0
        best_streak = score_row["best_streak"] if score_row else 0
        total_points = score_row["total_points"] if score_row else 0
        daily_streak = score_row["daily_streak"] if score_row else 0
        best_daily_streak = score_row["best_daily_streak"] if score_row else 0
        last_goal_date = score_row["last_goal_date"] if score_row else None

        # Pokud uživatel vynechal kalendářní den, denní streak se resetuje
        if last_goal_date and last_goal_date < yesterday_str:
            daily_streak = 0

        streak_bonus = 0
        if is_correct:
            current_streak += 1
            if current_streak > best_streak:
                best_streak = current_streak
            # Streak bonus od 5. správné v řadě
            if current_streak >= 5:
                streak_bonus = 2
                awarded_points += streak_bonus
        else:
            current_streak = 0

        # 5. Denní minimální postup (Daily Minimal Progress)
        conn.execute(
            """
            INSERT INTO daily_progress (user_id, activity_date, questions_answered, questions_correct, goal_met, updated_at)
            VALUES (?, ?, 1, ?, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, activity_date) DO UPDATE SET
                questions_answered = questions_answered + 1,
                questions_correct = questions_correct + excluded.questions_correct,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, today_str, 1 if is_correct else 0)
        )

        dp_row = conn.execute(
            "SELECT questions_answered, questions_correct, goal_met FROM daily_progress WHERE user_id = ? AND activity_date = ?",
            (user_id, today_str)
        ).fetchone()

        q_today = dp_row["questions_answered"] if dp_row else 1
        c_today = dp_row["questions_correct"] if dp_row else (1 if is_correct else 0)
        goal_already_met = bool(dp_row["goal_met"]) if dp_row else False
        daily_goal_just_met = False

        if q_today >= DAILY_MIN_GOAL and not goal_already_met:
            daily_goal_just_met = True
            goal_already_met = True
            conn.execute(
                "UPDATE daily_progress SET goal_met = 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND activity_date = ?",
                (user_id, today_str)
            )
            if last_goal_date == yesterday_str:
                daily_streak += 1
            elif last_goal_date == today_str:
                daily_streak = max(1, daily_streak)
            else:
                daily_streak = 1

            if daily_streak > best_daily_streak:
                best_daily_streak = daily_streak
            last_goal_date = today_str

        new_total_points = total_points + awarded_points

        # 6. Aktualizovat user_scores
        conn.execute(
            """
            INSERT INTO user_scores (
                user_id, total_points, current_streak, best_streak,
                daily_streak, best_daily_streak, last_goal_date, last_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                total_points = excluded.total_points,
                current_streak = excluded.current_streak,
                best_streak = excluded.best_streak,
                daily_streak = excluded.daily_streak,
                best_daily_streak = excluded.best_daily_streak,
                last_goal_date = excluded.last_goal_date,
                last_active = CURRENT_TIMESTAMP
            """,
            (user_id, new_total_points, current_streak, best_streak, daily_streak, best_daily_streak, last_goal_date)
        )

        # 7. Aktualizovat question_stats
        is_first_try_correct = 1 if (is_correct and attempt_number == 1) else 0
        conn.execute(
            """
            INSERT INTO question_stats (question_id, total_attempts, correct_attempts, first_try_correct)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                total_attempts = total_attempts + 1,
                correct_attempts = correct_attempts + excluded.correct_attempts,
                first_try_correct = first_try_correct + excluded.first_try_correct
            """,
            (question_id, 1 if is_correct else 0, is_first_try_correct)
        )

        # 8. Zapsat log odpovědi
        conn.execute(
            """
            INSERT INTO user_answers (user_id, question_id, is_correct, attempt_number, points_awarded)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, question_id, 1 if is_correct else 0, attempt_number, awarded_points)
        )

    return {
        "points_awarded": awarded_points,
        "base_points": base_points,
        "multiplier": multiplier,
        "difficulty": difficulty_label,
        "streak": current_streak,
        "streak_bonus": streak_bonus,
        "total_points": new_total_points,
        "daily_streak": daily_streak,
        "best_daily_streak": best_daily_streak,
        "questions_today": q_today,
        "correct_today": c_today,
        "daily_goal": DAILY_MIN_GOAL,
        "daily_goal_met": goal_already_met,
        "daily_goal_just_met": daily_goal_just_met
    }
