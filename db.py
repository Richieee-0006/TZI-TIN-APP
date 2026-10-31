import re
import os
import sqlite3
import random
import string
import secrets
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import bcrypt

BASE = Path(__file__).resolve().parent
DB_FILE = BASE / "tzi.db"
_local = threading.local()

THEME_DATA = {
    "games": {
        "label": "Hry",
        "adjectives": [
            "Mocný", "Hbitý", "Kybernetický", "Legendární", "Rychlý", "Moudrý", "Statečný",
            "Zlatý", "Nezdolný", "Bleskový", "Taktický", "Pixelový", "Pikantní", "Kritický", "Nezničitelný"
        ],
        "characters": [
            "Geralt", "Pikachu", "Steve", "Kratos", "Doomguy", "Mario", "Link", "Gordon Freeman",
            "Ezio", "Sephiroth", "Sans", "Pac-Man", "Master Chief", "Arthas", "Glados", "Sylvanas",
            "Lara Croft", "Rayman", "Crash Bandicoot", "Sonic", "Solid Snake", "Spyro"
        ]
    },
    "movies": {
        "label": "Filmy",
        "adjectives": [
            "Tajemný", "Odvážný", "Hvězdný", "Temný", "Kosmický", "Nesmrtelný", "Epický",
            "Kultovní", "Stínový", "Cestující", "Ostrý", "Sluneční", "Nenucený", "Filmový"
        ],
        "characters": [
            "Neo", "Gandalf", "Frodo", "Morpheus", "Aragorn", "Batman", "Joker", "Terminator",
            "Darth Vader", "Luke Skywalker", "Indiana Jones", "John Wick", "Han Solo", "Legolas",
            "Yoda", "Ripley", "Trinity", "Maximus", "Jack Sparrow", "Blade Runner"
        ]
    },
    "anime": {
        "label": "Anime",
        "adjectives": [
            "Kouzelný", "Divoký", "Veselý", "Ninjovský", "Duchovní", "Zářivý", "Chrabrý",
            "Mystický", "Cílevědomý", "Bojovný", "Roztomilý", "Neohrožený", "Mocný"
        ],
        "characters": [
            "Totoro", "Naruto", "Luffy", "Goku", "Levi", "Eren", "Saitama", "Spike Spiegel",
            "Kakashi", "Edward Elric", "Tanjiro", "Nezuko", "Gojo", "Light Yagami", "Mononoke",
            "Deku", "Zoro", "Shinji", "Killua", "Alphonse"
        ]
    },
    "series": {
        "label": "Seriály",
        "adjectives": [
            "Geniální", "Bláznivý", "Drsný", "Sarkastický", "Časový", "Nenápadný", "Důvtipný",
            "Záhadný", "Vyšetřující", "Nekonečný", "Chemický", "Královský"
        ],
        "characters": [
            "Walter White", "Heisenberg", "Sherlock", "Rimmer", "Lister", "Kryten", "Kocour",
            "Doctor Who", "Eleven", "Saul Goodman", "Tyrion", "Jesse Pinkman", "Crowley",
            "Rick Sanchez", "Morty", "Lucifer", "Peaky Blinder", "Dexter", "House MD"
        ]
    }
}


def get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(str(DB_FILE), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        _local.conn = conn
    return _local.conn


def close_db():
    if hasattr(_local, "conn") and _local.conn is not None:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None


def init_db():
    conn = get_db()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            theme TEXT NOT NULL DEFAULT 'games',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source TEXT NOT NULL,
            seen_json TEXT NOT NULL DEFAULT '{}',
            session_json TEXT DEFAULT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, source)
        );

        CREATE TABLE IF NOT EXISTS user_scores (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            total_points INTEGER NOT NULL DEFAULT 0,
            current_streak INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0,
            daily_streak INTEGER NOT NULL DEFAULT 0,
            best_daily_streak INTEGER NOT NULL DEFAULT 0,
            last_goal_date TEXT DEFAULT NULL,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_progress (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            activity_date TEXT NOT NULL,
            questions_answered INTEGER NOT NULL DEFAULT 0,
            questions_correct INTEGER NOT NULL DEFAULT 0,
            goal_met INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, activity_date)
        );

        CREATE TABLE IF NOT EXISTS koth_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            king_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            king_username TEXT,
            king_score INTEGER NOT NULL DEFAULT 0,
            king_correct INTEGER NOT NULL DEFAULT 0,
            king_time_ms INTEGER NOT NULL DEFAULT 0,
            crowned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            defenses_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS koth_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            challenger_username TEXT NOT NULL,
            defender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            defender_username TEXT,
            defender_score_before INTEGER NOT NULL DEFAULT 0,
            challenger_score INTEGER NOT NULL,
            correct_count INTEGER NOT NULL DEFAULT 0,
            total_questions INTEGER NOT NULL DEFAULT 10,
            time_ms INTEGER NOT NULL DEFAULT 0,
            won_throne INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            level TEXT NOT NULL,
            endpoint TEXT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            message TEXT NOT NULL,
            stack_trace TEXT
        );

        CREATE TABLE IF NOT EXISTS ffa_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            score INTEGER NOT NULL,
            correct_count INTEGER NOT NULL DEFAULT 0,
            total_questions INTEGER NOT NULL DEFAULT 10,
            time_ms INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS duel_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            creator_username TEXT NOT NULL,
            creator_score INTEGER NOT NULL DEFAULT 0,
            creator_correct INTEGER NOT NULL DEFAULT 0,
            creator_time_ms INTEGER NOT NULL DEFAULT 0,
            opponent_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            opponent_username TEXT,
            opponent_score INTEGER,
            opponent_correct INTEGER,
            opponent_time_ms INTEGER,
            question_ids_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'open',
            winner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            winner_username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS comp_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'ffa',
            host_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            host_username TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            max_players INTEGER NOT NULL DEFAULT 8,
            question_count INTEGER NOT NULL DEFAULT 10,
            source TEXT NOT NULL DEFAULT '',
            question_ids_json TEXT NOT NULL DEFAULT '[]',
            winner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            winner_username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS comp_room_players (
            room_id INTEGER NOT NULL REFERENCES comp_rooms(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            is_host INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'joined',
            score INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0,
            total_questions INTEGER NOT NULL DEFAULT 10,
            time_ms INTEGER NOT NULL DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            PRIMARY KEY (room_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS question_stats (
            question_id TEXT PRIMARY KEY,
            total_attempts INTEGER NOT NULL DEFAULT 0,
            correct_attempts INTEGER NOT NULL DEFAULT 0,
            first_try_correct INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question_id TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            attempt_number INTEGER NOT NULL DEFAULT 1,
            points_awarded INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_answers_user_q ON user_answers(user_id, question_id);
        CREATE INDEX IF NOT EXISTS idx_scores_points ON user_scores(total_points DESC);
        CREATE INDEX IF NOT EXISTS idx_daily_user_date ON daily_progress(user_id, activity_date);
        CREATE INDEX IF NOT EXISTS idx_koth_matches_created ON koth_matches(created_at DESC);
        """)
        for col_sql in (
            "ALTER TABLE user_scores ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE user_scores ADD COLUMN best_daily_streak INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE user_scores ADD COLUMN last_goal_date TEXT DEFAULT NULL",
        ):
            try:
                conn.execute(col_sql)
            except sqlite3.OperationalError:
                pass


def hash_password(password: str) -> str:
    pw_bytes = password.strip().encode("utf-8")[:72]
    salt = bcrypt.gensalt(12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    try:
        pw_bytes = password.strip().encode("utf-8")[:72]
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


def generate_unique_nickname(theme: str) -> str:
    conn = get_db()
    theme_info = THEME_DATA.get(theme, THEME_DATA["games"])
    adjectives = theme_info["adjectives"]
    characters = theme_info["characters"]

    for _ in range(60):
        adj = random.choice(adjectives)
        char = random.choice(characters)
        candidate = f"{adj} {char}"
        row = conn.execute("SELECT id FROM users WHERE username = ?", (candidate,)).fetchone()
        if not row:
            return candidate

    # If combinations are taken, add unique suffix
    for _ in range(100):
        adj = random.choice(adjectives)
        char = random.choice(characters)
        num = random.randint(10, 99)
        candidate = f"{adj} {char} {num}"
        row = conn.execute("SELECT id FROM users WHERE username = ?", (candidate,)).fetchone()
        if not row:
            return candidate

    return f"Student {secrets.token_hex(3).upper()}"


def register_user(
    theme: str = "games",
    password: str = "",
    username: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    conn = get_db()

    if username and username.strip():
        nickname = username.strip()
        if len(nickname) < 3 or len(nickname) > 25:
            return False, "Uživatelské jméno musí mít 3 až 25 znaků.", None
        if not re.match(r"^[A-Za-z0-9_áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ\-]+$", nickname):
            return False, "Jméno smí obsahovat pouze písmena, čísla, pomlčku a podtržítko.", None
        if nickname.lower() == "admin":
            return False, "Jméno 'admin' je vyhrazeno.", None
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? COLLATE NOCASE",
            (nickname,)
        ).fetchone()
        if existing:
            return False, "Toto uživatelské jméno je již obsazené.", None
    else:
        nickname = generate_unique_nickname(theme)

    pw_hash = hash_password(password)

    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role, theme) VALUES (?, ?, 'student', ?)",
                (nickname, pw_hash, theme)
            )
            user_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO user_scores (user_id, total_points, current_streak, best_streak, daily_streak, best_daily_streak) VALUES (?, 0, 0, 0, 0, 0)",
                (user_id,)
            )
        user = {"id": user_id, "username": nickname, "role": "student", "theme": theme}
        return True, None, user
    except sqlite3.IntegrityError:
        return False, "Toto uživatelské jméno je již obsazené.", None


def authenticate_user(username_or_code: str, password: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    ident = username_or_code.strip()
    row = conn.execute("SELECT id, username, password_hash, role, theme FROM users WHERE username = ? COLLATE NOCASE", (ident,)).fetchone()
    if row and check_password(password, row["password_hash"]):
        return dict(row)
    return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute("SELECT id, username, role, theme, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return dict(row)
    return None


def ensure_admin_exists(admin_password_hash: str):
    """Vytvoří výchozího admin účet 'admin' pokud neexistuje."""
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()
    if not row:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role, theme) VALUES ('Admin', ?, 'admin', 'games')",
                (admin_password_hash,)
            )
            user_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO user_scores (user_id, total_points, current_streak, best_streak) VALUES (?, 0, 0, 0)",
                (user_id,)
            )


def verify_user_password(user_id: int, password: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not password:
        return False
    return check_password(password, row["password_hash"])


def update_username(user_id: int, new_username: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    clean = (new_username or "").strip()
    if len(clean) < 3 or len(clean) > 25:
        return False, "Uživatelské jméno musí mít 3 až 25 znaků.", None
    if not re.match(r"^[A-Za-z0-9_áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ\-]+$", clean):
        return False, "Jméno smí obsahovat pouze písmena, čísla, pomlčku a podtržítko.", None
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ? COLLATE NOCASE AND id != ?",
        (clean, user_id)
    ).fetchone()
    if existing:
        return False, "Toto uživatelské jméno již používá někdo jiný.", None
    try:
        with conn:
            conn.execute("UPDATE users SET username = ? WHERE id = ?", (clean, user_id))
        return True, None, get_user_by_id(user_id)
    except Exception:
        return False, "Nepodařilo se změnit uživatelské jméno.", None


def update_password(user_id: int, current_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
    if not verify_user_password(user_id, current_password):
        return False, "Současné heslo není správné."
    if not new_password or len(new_password) < 8:
        return False, "Nové heslo musí mít alespoň 6 znaků."
    new_hash = hash_password(new_password)
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    return True, None


def clear_user_progress_db(user_id: int, source: Optional[str] = None) -> None:
    conn = get_db()
    with conn:
        if source and source != "_all":
            conn.execute("DELETE FROM user_progress WHERE user_id = ? AND source = ?", (user_id, source))
        else:
            conn.execute("DELETE FROM user_progress WHERE user_id = ?", (user_id,))


def get_user_all_progress_map(user_id: int) -> Dict[str, Dict[str, str]]:
    conn = get_db()
    rows = conn.execute("SELECT source, seen_json FROM user_progress WHERE user_id = ?", (user_id,)).fetchall()
    out: Dict[str, Dict[str, str]] = {}
    import json
    for r in rows:
        try:
            data = json.loads(r["seen_json"] or "{}")
            if isinstance(data, dict):
                out[r["source"]] = data
        except Exception:
            pass
    return out


def delete_user_account(user_id: int) -> None:
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM user_progress WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_answers WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM daily_progress WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_scores WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM comp_room_players WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM comp_rooms WHERE host_id = ?", (user_id,))
        conn.execute("DELETE FROM ffa_runs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM duel_matches WHERE creator_id = ? OR opponent_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def log_error(level: str, message: str, endpoint: Optional[str] = None, user_id: Optional[int] = None, stack_trace: Optional[str] = None) -> None:
    try:
        conn = get_db()
        with conn:
            conn.execute(
                """
                INSERT INTO error_logs (level, endpoint, user_id, message, stack_trace)
                VALUES (?, ?, ?, ?, ?)
                """,
                (level, endpoint, user_id, message, stack_trace)
            )
    except Exception:
        # Nikdy nezhodit request, pokud tabulka v testovacím DB ještě nebyla inicializována
        pass


def get_recent_errors(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, created_at, level, endpoint, user_id, message, stack_trace
        FROM error_logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]

