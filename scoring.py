import math
from datetime import date, timedelta
from typing import Dict, Any, Optional, Tuple, List
from db import get_db

DAILY_MIN_GOAL = 5
KOTH_DEFAULT_QUESTIONS = 10


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



# ==============================================================================
# KOMPETITIVNÍ LOBBY & ROOMS (FFA, 1v1 Duel, King of the Hill)
# ==============================================================================

def _format_room(conn, room_row) -> Dict[str, Any]:
    import json
    if not room_row:
        return {}
    r = dict(room_row)
    rid = r["id"]
    players_rows = conn.execute(
        """
        SELECT user_id, username, is_host, status, score, correct_count, total_questions, time_ms, joined_at, finished_at
        FROM comp_room_players
        WHERE room_id = ?
        ORDER BY CASE WHEN status = 'finished' THEN 0 ELSE 1 END, score DESC, time_ms ASC, is_host DESC, joined_at ASC
        """,
        (rid,)
    ).fetchall()
    players = [dict(p) for p in players_rows]
    try:
        q_ids = json.loads(r.get("question_ids_json") or "[]")
    except Exception:
        q_ids = []
    return {
        "id": rid,
        "name": r["name"],
        "mode": r["mode"],
        "host_id": r["host_id"],
        "host_username": r["host_username"],
        "status": r["status"],
        "max_players": r["max_players"],
        "question_count": r["question_count"],
        "source": r.get("source") or "",
        "question_ids": q_ids,
        "player_count": len(players),
        "players": players,
        "winner_id": r.get("winner_id"),
        "winner_username": r.get("winner_username"),
        "created_at": r.get("created_at"),
        "started_at": r.get("started_at"),
        "completed_at": r.get("completed_at"),
    }


def list_comp_rooms(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Vrátí seznam čekajících, probíhajících a nedávno dokončených místností v lobby."""
    conn = get_db()
    active_rows = conn.execute(
        """
        SELECT * FROM comp_rooms
        WHERE status IN ('waiting', 'in_progress')
        ORDER BY CASE WHEN status = 'waiting' THEN 0 ELSE 1 END, id DESC
        LIMIT 20
        """
    ).fetchall()
    recent_rows = conn.execute(
        """
        SELECT * FROM comp_rooms
        WHERE status = 'completed'
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()
    return {
        "active_rooms": [_format_room(conn, row) for row in active_rows],
        "recent_rooms": [_format_room(conn, row) for row in recent_rows],
    }


def get_comp_room(room_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute("SELECT * FROM comp_rooms WHERE id = ?", (int(room_id),)).fetchone()
    if not row:
        return None
    return _format_room(conn, row)


def create_comp_room(
    user_id: int,
    username: str,
    mode: str = "ffa",
    name: str = "",
    question_count: int = KOTH_DEFAULT_QUESTIONS,
    source: str = "",
    question_ids: Optional[List[str]] = None,
    max_players: Optional[int] = None,
) -> Dict[str, Any]:
    """Vytvoří novou kompetitivní místnost v lobby a nastaví zakladatele jako 👑 hostitele."""
    import json
    conn = get_db()
    mode_clean = mode if mode in ("ffa", "duel", "koth") else "ffa"
    mode_labels = {"ffa": "Free For All", "duel": "1v1 Duel", "koth": "King of the Hill"}
    room_name = (name or "").strip()[:60] or f"{mode_labels[mode_clean]} – {username}"
    max_p = int(max_players) if max_players else (2 if mode_clean == "duel" else 8)
    max_p = max(2, min(16, max_p))
    q_count = max(1, min(30, int(question_count or KOTH_DEFAULT_QUESTIONS)))

    with conn:
        cur = conn.execute(
            """
            INSERT INTO comp_rooms (name, mode, host_id, host_username, status, max_players, question_count, source, question_ids_json)
            VALUES (?, ?, ?, ?, 'waiting', ?, ?, ?, ?)
            """,
            (room_name, mode_clean, user_id, username, max_p, q_count, source or "", json.dumps(question_ids or []))
        )
        room_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO comp_room_players (room_id, user_id, username, is_host, status, total_questions)
            VALUES (?, ?, ?, 1, 'joined', ?)
            """,
            (room_id, user_id, username, q_count)
        )

    return get_comp_room(room_id)


def join_comp_room(room_id: int, user_id: int, username: str, auto_start_duel: bool = False) -> Dict[str, Any]:
    """Připojí hráče do čekající místnosti v lobby."""
    conn = get_db()
    with conn:
        row = conn.execute("SELECT * FROM comp_rooms WHERE id = ?", (int(room_id),)).fetchone()
        if not row:
            return {"ok": False, "error": "Místnost neexistuje."}

        existing = conn.execute(
            "SELECT * FROM comp_room_players WHERE room_id = ? AND user_id = ?",
            (int(room_id), user_id)
        ).fetchone()

        if row["status"] != "waiting" and not existing:
            return {"ok": False, "error": "Tato místnost již byla spuštěna nebo ukončena."}

        if not existing:
            cnt_row = conn.execute(
                "SELECT COUNT(*) AS c FROM comp_room_players WHERE room_id = ?",
                (int(room_id),)
            ).fetchone()
            cur_count = cnt_row["c"] if cnt_row else 0
            if cur_count >= row["max_players"]:
                return {"ok": False, "error": "Místnost je již plná."}

            conn.execute(
                """
                INSERT INTO comp_room_players (room_id, user_id, username, is_host, status, total_questions)
                VALUES (?, ?, ?, 0, 'joined', ?)
                """,
                (int(room_id), user_id, username, row["question_count"])
            )

        if auto_start_duel and row["mode"] == "duel":
            cnt_after = conn.execute(
                "SELECT COUNT(*) AS c FROM comp_room_players WHERE room_id = ?",
                (int(room_id),)
            ).fetchone()["c"]
            if cnt_after >= 2 and row["status"] == "waiting":
                conn.execute(
                    "UPDATE comp_rooms SET status = 'in_progress', started_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(room_id),)
                )
                conn.execute(
                    "UPDATE comp_room_players SET status = 'playing' WHERE room_id = ?",
                    (int(room_id),)
                )

    return {"ok": True, "room": get_comp_room(room_id)}


def start_comp_room(room_id: int, user_id: int) -> Dict[str, Any]:
    """Hostitel (👑) spustí hru pro všechny připojené hráče v místnosti."""
    conn = get_db()
    with conn:
        row = conn.execute("SELECT * FROM comp_rooms WHERE id = ?", (int(room_id),)).fetchone()
        if not row:
            return {"ok": False, "error": "Místnost neexistuje."}
        if row["host_id"] != user_id:
            return {"ok": False, "error": "Pouze zakladatel místnosti (👑) může hru spustit."}
        if row["status"] == "waiting":
            conn.execute(
                "UPDATE comp_rooms SET status = 'in_progress', started_at = CURRENT_TIMESTAMP WHERE id = ?",
                (int(room_id),)
            )
            conn.execute(
                "UPDATE comp_room_players SET status = 'playing' WHERE room_id = ?",
                (int(room_id),)
            )
    return {"ok": True, "room": get_comp_room(room_id)}


def leave_comp_room(room_id: int, user_id: int) -> Dict[str, Any]:
    """Hráč opustí místnost. Pokud odejde 👑 hostitel z čekající místnosti, předá se korunka dalšímu hráči nebo se prázdná místnost zruší."""
    conn = get_db()
    with conn:
        row = conn.execute("SELECT * FROM comp_rooms WHERE id = ?", (int(room_id),)).fetchone()
        if not row:
            return {"ok": True, "deleted": True}
        conn.execute(
            "DELETE FROM comp_room_players WHERE room_id = ? AND user_id = ?",
            (int(room_id), user_id)
        )
        rem = conn.execute(
            "SELECT * FROM comp_room_players WHERE room_id = ? ORDER BY joined_at ASC",
            (int(room_id),)
        ).fetchall()
        if not rem:
            conn.execute("DELETE FROM comp_rooms WHERE id = ?", (int(room_id),))
            return {"ok": True, "deleted": True}
        if row["host_id"] == user_id:
            new_host = rem[0]
            conn.execute(
                "UPDATE comp_rooms SET host_id = ?, host_username = ? WHERE id = ?",
                (new_host["user_id"], new_host["username"], int(room_id))
            )
            conn.execute(
                "UPDATE comp_room_players SET is_host = 1 WHERE room_id = ? AND user_id = ?",
                (int(room_id), new_host["user_id"])
            )
    return {"ok": True, "deleted": False, "room": get_comp_room(room_id)}


def submit_comp_room_result(
    room_id: int,
    user_id: int,
    username: str,
    correct_count: int,
    total_questions: int,
    time_ms: int = 0,
    explicit_score: Optional[int] = None,
) -> Dict[str, Any]:
    """Zaznamená výsledek hráče v místnosti, aktualizuje pořadí v místnosti i globální statistiky daného režimu."""
    conn = get_db()
    row = conn.execute("SELECT * FROM comp_rooms WHERE id = ?", (int(room_id),)).fetchone()
    if not row:
        return {"ok": False, "error": "Místnost neexistuje."}

    time_ms_clean = max(0, int(time_ms or 0))
    correct_clean = max(0, int(correct_count or 0))
    total_clean = max(1, int(total_questions or row["question_count"] or KOTH_DEFAULT_QUESTIONS))

    if explicit_score is not None:
        score = max(0, int(explicit_score))
    else:
        speed_bonus = max(0, 120 - (time_ms_clean // 1000)) if correct_clean > 0 else 0
        score = correct_clean * 100 + speed_bonus

    mode = row["mode"]
    with conn:
        existing = conn.execute(
            "SELECT * FROM comp_room_players WHERE room_id = ? AND user_id = ?",
            (int(room_id), user_id)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE comp_room_players
                SET status = 'finished', score = ?, correct_count = ?, total_questions = ?, time_ms = ?, finished_at = CURRENT_TIMESTAMP
                WHERE room_id = ? AND user_id = ?
                """,
                (score, correct_clean, total_clean, time_ms_clean, int(room_id), user_id)
            )
        else:
            conn.execute(
                """
                INSERT INTO comp_room_players (room_id, user_id, username, is_host, status, score, correct_count, total_questions, time_ms, finished_at)
                VALUES (?, ?, ?, 0, 'finished', ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (int(room_id), user_id, username, score, correct_clean, total_clean, time_ms_clean)
            )

        p_rows = conn.execute(
            """
            SELECT * FROM comp_room_players
            WHERE room_id = ?
            ORDER BY CASE WHEN status = 'finished' THEN 0 ELSE 1 END, score DESC, time_ms ASC
            """,
            (int(room_id),)
        ).fetchall()

        all_finished = len(p_rows) > 0 and all(p["status"] == "finished" for p in p_rows)
        finished_rows = [p for p in p_rows if p["status"] == "finished"]
        leader = finished_rows[0] if finished_rows else None

        if all_finished and leader:
            conn.execute(
                """
                UPDATE comp_rooms
                SET status = 'completed', winner_id = ?, winner_username = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (leader["user_id"], leader["username"], int(room_id))
            )

    # Propíšeme i do globální tabulky příslušného kompetitivního režimu
    mode_res = {}
    if mode == "koth":
        mode_res = submit_koth_challenge(user_id, username, correct_clean, total_clean, time_ms_clean, explicit_score=score)
    elif mode == "ffa":
        mode_res = submit_ffa_run(user_id, username, correct_clean, total_clean, time_ms_clean, explicit_score=score)
    elif mode == "duel":
        mode_res = submit_duel_match(user_id, username, correct_clean, total_clean, time_ms_clean, explicit_score=score)

    room_after = get_comp_room(room_id)
    rank_in_room = 1
    for idx, p in enumerate(room_after.get("players", []), 1):
        if p["user_id"] == user_id:
            rank_in_room = idx
            break

    return {
        "ok": True,
        "room_id": int(room_id),
        "mode": mode,
        "score": score,
        "challenger_score": score,
        "my_score": score,
        "correct_count": correct_clean,
        "total_questions": total_clean,
        "time_ms": time_ms_clean,
        "rank": rank_in_room,
        "is_leader": rank_in_room == 1,
        "won_throne": mode_res.get("won_throne", rank_in_room == 1),
        "previous_king_score": mode_res.get("previous_king_score", 0),
        "resolved": room_after.get("status") == "completed",
        "won_duel": rank_in_room == 1 and room_after.get("status") == "completed",
        "room": room_after,
        "mode_result": mode_res,
    }
