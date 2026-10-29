import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from fastapi.testclient import TestClient
import server
import db

def test_full_pipeline():
    db.close_db()
    test_db = BASE / "test_temp_api.db"
    if test_db.exists():
        test_db.unlink()
    db.DB_FILE = test_db
    db.init_db()

    client = TestClient(server.app)

    print("--- [1] Test GET / unauthenticated -> Redirect to /login ---")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 or r.status_code == 302 or r.status_code == 303, f"Status: {r.status_code}"
    assert "/login" in r.headers["location"]
    print("OK: Nepřihlášený uživatel přesměrován na /login.")

    print("\n--- [2] Test GET /login & /register ---")
    r_login = client.get("/login")
    assert r_login.status_code == 200
    assert "TZI Trenér" in r_login.text

    r_reg = client.get("/register")
    assert r_reg.status_code == 200
    assert "Registrace" in r_reg.text
    assert 'name="invite_code"' not in r_reg.text
    print("OK: Stránky pro přihlášení a registraci (bez pozvánky) fungují.")

    print("\n--- [3] Otevřená registrace nového studenta bez pozvánky ---")
    reg_resp = client.post("/register", data={
        "theme": "movies",
        "password": "mypassword123"
    }, follow_redirects=False)
    assert reg_resp.status_code == 303, f"Status: {reg_resp.status_code}"
    cookie = reg_resp.cookies.get(server.SESSION_COOKIE)
    assert cookie is not None, "Session cookie musí být nastavena po registraci!"
    print("OK: Registrace proběhla, session cookie nastavena.")

    print("\n--- [4] Test přihlášeného studenta: GET /api/me ---")
    client.cookies.set(server.SESSION_COOKIE, cookie)
    me_resp = client.get("/api/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    print(f"Přiřazená přezdívka: {me_data['username']} (Téma: {me_data['theme']})")
    assert me_data["rank"] >= 1

    print("\n--- [5] Test kvízových API (/api/sources, /api/questions, /api/recall) ---")
    s_resp = client.get("/api/sources")
    assert s_resp.status_code == 200
    sources = s_resp.json()["sources"]
    print(f"Počet zdrojů přednášek: {len(sources)}")
    assert len(sources) > 0

    first_src = sources[0]["id"]
    q_resp = client.get(f"/api/questions?source={first_src}")
    assert q_resp.status_code == 200
    questions = q_resp.json()
    print(f"Otázek v {first_src}: {len(questions)}")

    print("\n--- [6] Test odeslání odpovědi s výpočtem bodů (POST /api/progress) ---")
    test_q_id = questions[0]["id"] if questions else "test_q"
    prog_resp = client.post("/api/progress?source=" + first_src, json={
        "seen": {test_q_id: "correct"},
        "session": None,
        "latest": {"id": test_q_id, "isCorrect": True}
    })
    assert prog_resp.status_code == 200
    prog_data = prog_resp.json()
    assert prog_data["ok"] is True
    assert prog_data["score"] is not None
    assert prog_data["score"]["points_awarded"] == 3
    print(f"OK: Získáno {prog_data['score']['points_awarded']} b, streak: {prog_data['score']['streak']}")

    print("\n--- [7] Test Leaderboard endpointu (/api/leaderboard) ---")
    lb_resp = client.get("/api/leaderboard")
    assert lb_resp.status_code == 200
    lb_data = lb_resp.json()
    print(f"Leaderboard: #{lb_data['rank']} z {lb_data['total']} studentů ({lb_data['points']} b)")
    assert lb_data["points"] == 3

    print("\n--- [8] Test PWA endpointů (/manifest.webmanifest, /sw.js, /icon.svg) ---")
    r_man = client.get("/manifest.webmanifest")
    assert r_man.status_code == 200
    assert "TZI Trenér" in r_man.json()["name"]

    r_sw = client.get("/sw.js")
    assert r_sw.status_code == 200
    assert "CACHE_NAME" in r_sw.text

    r_icon = client.get("/icon.svg")
    assert r_icon.status_code == 200
    assert "<svg" in r_icon.text
    print("OK: PWA manifest, service worker a ikona fungují.")

    print("\n--- [9] Test Offline Sync s Anti-spoofing kontrolou (/api/sync) ---")
    # Zkusíme poslat odpověď: jedna správná a jedna zfalšovaná (špatná volba označená jako isCorrect=True)
    q_choice = [q for q in questions if q.get("type") == "choice"][0]
    q_id_choice = q_choice["id"]
    correct_opts = q_choice["correct"]

    # Falešná odpověď: uživatel pošle neplatnou volbu ['Z']
    sync_resp_fake = client.post("/api/sync", json={
        "source": first_src,
        "seen": {q_id_choice: "wrong"},
        "answers": [
            {"id": q_id_choice, "user_answer": ["Z"], "isCorrect": True}
        ]
    })
    assert sync_resp_fake.status_code == 200
    assert sync_resp_fake.json()["points_awarded"] == 0, "Anti-spoofing musí odmítnout body pro neplatnou odpověď!"

    # Pravá odpověď: uživatel pošle správnou volbu
    sync_resp_real = client.post("/api/sync", json={
        "source": first_src,
        "seen": {q_id_choice: "correct"},
        "answers": [
            {"id": q_id_choice, "user_answer": correct_opts, "isCorrect": True}
        ]
    })
    assert sync_resp_real.status_code == 200
    sync_data = sync_resp_real.json()
    assert sync_data["synced_count"] == 1
    assert sync_data["leaderboard"] is not None
    print(f"OK: Anti-spoofing ověření funguje. Body po synchronizaci: {sync_data['leaderboard']['points']} b.")

    print("\n=======================================================")
    print("  FASTAPI PIPELINE KOMPLETNĚ OTESTOVÁNA A FUNKČNÍ! :3 ")
    print("=======================================================")

    db.close_db()
    try:
        if test_db.exists():
            test_db.unlink()
    except Exception:
        pass

if __name__ == "__main__":
    test_full_pipeline()
