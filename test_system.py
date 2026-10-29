import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import db
import scoring

def run_tests():
    db.close_db()
    test_db = BASE / "test_temp.db"
    if test_db.exists():
        test_db.unlink()
    db.DB_FILE = test_db

    print("--- [1/6] Inicializace testovací DB ---")
    db.init_db()
    print("OK: Tabulky vytvořeny.")

    print("\n--- [2/6] Otevřená registrace studenta bez pozvánky (Téma: anime) ---")
    ok, err, user = db.register_user(theme="anime", password="secure_password123")
    assert ok, f"Registrace selhala: {err}"
    assert user is not None
    print(f"OK: Uživatel zaregistrován s vygenerovanou přezdívkou: '{user['username']}' (ID: {user['id']})")

    print("\n--- [3/6] Registrace druhého studenta bez pozvánky (Téma: games) ---")
    ok2, err2, user2 = db.register_user(theme="games", password="another_password")
    assert ok2, f"Druhá registrace selhala: {err2}"
    assert user2 is not None and user2["username"] != user["username"]
    print(f"OK: Druhý uživatel zaregistrován: '{user2['username']}'")

    print("\n--- [4/6] Autentizace studenta ---")
    auth_user = db.authenticate_user(user["username"], "secure_password123")
    assert auth_user is not None, "Autentizace správným heslem musí projít!"
    bad_auth = db.authenticate_user(user["username"], "wrong_password")
    assert bad_auth is None, "Autentizace špatným heslem nesmí projít!"
    print("OK: Přihlášení funguje.")

    print("\n--- [6/6] Testování bodovacího enginu & streaku ---")
    u_id = user["id"]
    # 1. otázka správně (1. pokus) -> 3 body
    res1 = scoring.record_question_answer(u_id, "q_test_1", is_correct=True)
    assert res1["points_awarded"] == 3, f"Očekávány 3 body, získáno {res1['points_awarded']}"
    assert res1["streak"] == 1

    # 4 další správné otázky -> dosáhne streaku 5
    scoring.record_question_answer(u_id, "q_test_2", is_correct=True)
    scoring.record_question_answer(u_id, "q_test_3", is_correct=True)
    scoring.record_question_answer(u_id, "q_test_4", is_correct=True)
    res5 = scoring.record_question_answer(u_id, "q_test_5", is_correct=True)
    # Streak 5 má bonus +2 body -> 3 + 2 = 5 bodů
    assert res5["streak"] == 5, f"Streak by měl být 5, je {res5['streak']}"
    assert res5["streak_bonus"] == 2, f"Streak bonus by měl být 2, je {res5['streak_bonus']}"
    assert res5["points_awarded"] == 5, f"Očekáváno 5 bodů se streak bonusem, získáno {res5['points_awarded']}"

    # Doplňovačka recall -> 5 base bodů + streak bonus 2 = 7 bodů
    res_rec = scoring.record_question_answer(u_id, "r-recall-1", is_correct=True)
    assert res_rec["base_points"] == 5
    assert res_rec["streak_bonus"] == 2
    assert res_rec["points_awarded"] == 7

    # Chybná odpověď -> streak se resetuje na 0
    res_wrong = scoring.record_question_answer(u_id, "q_test_fail", is_correct=False)
    assert res_wrong["streak"] == 0
    assert res_wrong["points_awarded"] == 0

    # Leaderboard pozice
    leaderboard = scoring.get_user_leaderboard_position(u_id)
    assert leaderboard["rank"] >= 1
    assert leaderboard["points"] > 0
    print(f"OK: Skóre: {leaderboard['points']} b, Streak: {leaderboard['current_streak']}, Nejlepší: {leaderboard['best_streak']}")
    print(f"OK: Pozice v žebříčku: #{leaderboard['rank']} z {leaderboard['total']}")

    print("\n==========================================")
    print("  VŠECHNY TESTY ÚSPĚŠNĚ PROŠLY! (100% OK)")
    print("==========================================")

    db.close_db()
    if test_db.exists():
        test_db.unlink()

def test_system_core():
    run_tests()

if __name__ == "__main__":
    run_tests()
