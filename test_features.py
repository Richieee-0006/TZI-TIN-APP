import subprocess
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import db
import scoring
import server


@pytest.fixture()
def temp_env(tmp_path):
    db.close_db()
    test_db = tmp_path / "test_features.db"
    old_db = db.DB_FILE
    db.DB_FILE = test_db
    db.init_db()
    client = TestClient(server.app)
    yield client
    db.close_db()
    db.DB_FILE = old_db


def test_r1_latex_katex_rendering():
    """R1: Ověření podpory LaTeXu (KaTeX) v ui/novy.html a neporušení běžného formátování."""
    novy_html = (BASE / "ui" / "novy.html").read_text(encoding="utf-8")
    assert "katex.min.css" in novy_html
    assert "katex.min.js" in novy_html

    node_check = r"""
    const fs = require('fs'), vm = require('vm'), assert = require('assert');
    const html = fs.readFileSync('ui/novy.html', 'utf8');
    const js = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
    const ctx = vm.createContext({
      document: { getElementById: () => ({ style: {}, classList: { add(){}, remove(){} }, addEventListener(){} }), addEventListener(){}, querySelectorAll: () => [] },
      localStorage: { getItem: () => null, setItem(){} },
      fetch: () => new Promise(() => {}),
      setTimeout, setInterval, clearInterval,
      katex: {
        renderToString: (tex, opts) => `<span class="katex-rendered" data-display="${opts.displayMode}">${tex}</span>`
      }
    });
    vm.runInContext(js, ctx);
    const fmt = vm.runInContext('fmt', ctx);

    // 1. LaTeX vzorec nesmí mít rozbité podtržítko, stříšku ani nerovnost
    const outLatex = fmt('Platí $a_{n-1} + x^2 < y$ v posloupnosti.');
    assert(outLatex.includes('<span class="katex-rendered" data-display="false">a_{n-1} + x^2 < y</span>'), 'Chybné vykreslení inline LaTeXu: ' + outLatex);

    // 2. Display LaTeX $$...$$
    const outDisplay = fmt('Vzorec: $$\\sum_{i=1}^n i$$');
    assert(outDisplay.includes('<span class="katex-rendered" data-display="true">\\sum_{i=1}^n i</span>'), 'Chybné vykreslení display LaTeXu: ' + outDisplay);

    // 3. Běžný text bez LaTeXu si zachová dolní/horní indexy a šipky
    const outPlain = fmt('Posloupnost a_n -> Z^2');
    assert(outPlain.includes('a<sub>n</sub>') && outPlain.includes('→') && outPlain.includes('Z<sup>2</sup>'), 'Rozbité běžné formátování: ' + outPlain);
    """
    res = subprocess.run(["node", "-e", node_check], cwd=str(BASE), capture_output=True, text=True)
    assert res.returncode == 0, f"Node KaTeX test selhal: {res.stderr}\n{res.stdout}"


def test_r2_daily_minimal_progress_and_streak_reset(temp_env):
    """R2: Ověření denního minimálního postupu, inkrementace denního streaku a resetu při vynechání dne."""
    ok, err, user = db.register_user(theme="games", password="heslo123")
    assert ok and user is not None
    uid = user["id"]

    # Den 1: 2026-10-20 — 4 otázky (ještě pod cílem 5 otázek)
    for i in range(4):
        r = scoring.record_question_answer(uid, f"1-{i+1}", True, activity_date="2026-10-20")
        assert r["daily_goal_met"] is False
        assert r["daily_streak"] == 0

    # 5. otázka v Den 1 -> splní denní cíl, streak = 1
    r5 = scoring.record_question_answer(uid, "1-5", True, activity_date="2026-10-20")
    assert r5["daily_goal_met"] is True
    assert r5["daily_goal_just_met"] is True
    assert r5["daily_streak"] == 1

    # Den 2: 2026-10-21 (následující kalendářní den) -> splnění cíle zvýší streak na 2
    for i in range(scoring.DAILY_MIN_GOAL):
        r_d2 = scoring.record_question_answer(uid, f"2-{i+1}", True, activity_date="2026-10-21")
    assert r_d2["daily_goal_met"] is True
    assert r_d2["daily_streak"] == 2
    assert r_d2["best_daily_streak"] == 2

    # Den 3 (2026-10-22) je VYNECHÁN. Kontrola dne 2026-10-23 musí ukázat resetovaný denní streak = 0!
    dp_after_skip = scoring.get_daily_progress(uid, today_str="2026-10-23")
    assert dp_after_skip["daily_streak"] == 0
    assert dp_after_skip["best_daily_streak"] == 2
    assert dp_after_skip["goal_met"] is False

    # Splnění cíle 2026-10-23 nastaví nový streak na 1
    for i in range(scoring.DAILY_MIN_GOAL):
        r_d4 = scoring.record_question_answer(uid, f"3-{i+1}", True, activity_date="2026-10-23")
    assert r_d4["daily_streak"] == 1
    assert r_d4["best_daily_streak"] == 2


def test_r3_king_of_the_hill_1v1(temp_env):
    """R3: Ověření asynchronního kompetitivního režimu King of the Hill 1v1 a přebírání kopce."""
    client = temp_env

    # Zaregistrovat Hráče 1 a Hráče 2
    r1 = client.post("/register", data={"theme": "games", "password": "password1"}, follow_redirects=False)
    cookie1 = r1.cookies.get(server.SESSION_COOKIE)

    r2 = client.post("/register", data={"theme": "anime", "password": "password2"}, follow_redirects=False)
    cookie2 = r2.cookies.get(server.SESSION_COOKIE)

    # Hráč 1 spustí KotH a obsadí volný trůn
    client.cookies.set(server.SESSION_COOKIE, cookie1)
    me1 = client.get("/api/me").json()
    start_resp = client.post("/api/koth/start", json={"count": 5})
    assert start_resp.status_code == 200
    assert len(start_resp.json()["questions"]) > 0

    sub1 = client.post("/api/koth/submit", json={
        "correct_count": 6,
        "total_questions": 10,
        "time_ms": 30000
    })
    assert sub1.status_code == 200
    d1 = sub1.json()
    assert d1["won_throne"] is True
    assert d1["king"]["username"] == me1["username"]
    king1_score = d1["challenger_score"]

    # Hráč 2 zkusí vyzvat krále, ale získá nižší skóre -> Král 1 ubrání kopec
    client.cookies.set(server.SESSION_COOKIE, cookie2)
    me2 = client.get("/api/me").json()
    sub2_fail = client.post("/api/koth/submit", json={
        "correct_count": 3,
        "total_questions": 10,
        "time_ms": 45000
    })
    assert sub2_fail.status_code == 200
    d2_fail = sub2_fail.json()
    assert d2_fail["won_throne"] is False
    assert d2_fail["king"]["username"] == me1["username"]
    assert d2_fail["king"]["defenses_count"] == 1

    # Hráč 2 dá lepší výsledek (9/10 rychle) -> sesadí Hráče 1 a stane se novým Králem kopce!
    sub2_win = client.post("/api/koth/submit", json={
        "correct_count": 9,
        "total_questions": 10,
        "time_ms": 15000
    })
    assert sub2_win.status_code == 200
    d2_win = sub2_win.json()
    assert d2_win["won_throne"] is True
    assert d2_win["challenger_score"] > king1_score
    assert d2_win["king"]["username"] == me2["username"]
    assert d2_win["king"]["defenses_count"] == 0

    # Ověření přes GET /api/koth/status
    st = client.get("/api/koth/status").json()
    assert st["king"]["username"] == me2["username"]
    assert len(st["recent_matches"]) == 3


def test_r4_open_registration_and_relogin_without_invite(temp_env):
    """R4: Ověření registrace bez pozvánkového kódu a následného přihlášení."""
    client = temp_env

    reg_page = client.get("/register")
    assert reg_page.status_code == 200
    assert 'name="invite_code"' not in reg_page.text

    reg_res = client.post("/register", data={"theme": "series", "password": "super_secret_pw"}, follow_redirects=False)
    assert reg_res.status_code == 303
    session_cookie = reg_res.cookies.get(server.SESSION_COOKIE)
    assert session_cookie is not None

    client.cookies.set(server.SESSION_COOKIE, session_cookie)
    me = client.get("/api/me").json()
    assigned_username = me["username"]
    assert assigned_username and me["theme"] == "series"

    # Odhlášení a opětovné přihlášení přes /login
    client.get("/logout")
    client.cookies.clear()

    login_res = client.post("/login", data={"username": assigned_username, "password": "super_secret_pw"}, follow_redirects=False)
    assert login_res.status_code == 303
    new_cookie = login_res.cookies.get(server.SESSION_COOKIE)
    assert new_cookie is not None

    client.cookies.set(server.SESSION_COOKIE, new_cookie)
    me_again = client.get("/api/me").json()
    assert me_again["username"] == assigned_username


def test_r5_wasm_binary_and_client_logic(temp_env):
    """R5: Ověření WebAssembly modulu (zdrojový kód, sestavená binárka, HTTP endpoint a běh v JS/WASM)."""
    client = temp_env
    wasm_src = BASE / "wasm" / "quiz_core.ts"
    wasm_bin = BASE / "ui" / "quiz.wasm"
    build_script = BASE / "build_wasm.py"

    assert wasm_src.exists(), "Chybí zdrojový kód WASM modulu"
    assert wasm_bin.exists(), "Chybí zkompilovaný ui/quiz.wasm"
    assert build_script.exists(), "Chybí sestavovací skript build_wasm.py"

    # Ověřit HTTP servírování /quiz.wasm
    resp = client.get("/quiz.wasm")
    assert resp.status_code == 200
    assert resp.content[:4] == b"\x00asm"

    # Spustit kompletní klientský test test_doplnovacka.js běžící nad WASM jádrem
    proc = subprocess.run(["node", "test_doplnovacka.js"], cwd=str(BASE), capture_output=True, text=True)
    assert proc.returncode == 0, f"test_doplnovacka.js selhal:\n{proc.stdout}\n{proc.stderr}"
    assert "chyb: 0" in proc.stdout


def test_r6_all_competitive_modes_and_classic_registration(temp_env):
    """R6: Ověření všech kompetitivních režimů (FFA, 1v1 Duel, KotH), klasické registrace se jménem a odstranění starého vzhledu."""
    client = temp_env

    # 1. Starý vzhled (klasicky.html) je pryč
    assert not (BASE / "ui" / "klasicky.html").exists()
    novy_html = (BASE / "ui" / "novy.html").read_text(encoding="utf-8")
    assert "Starý vzhled" not in novy_html
    assert "startCompetitiveMode('ffa')" in novy_html
    assert "startCompetitiveMode('duel')" in novy_html
    assert "startKothChallenge()" in novy_html

    # 2. Klasická registrace s vlastním uživatelským jménem a potvrzením hesla
    r1 = client.post("/register", data={
        "username": "Alchymista_CZ",
        "password": "password123",
        "password_confirm": "password123"
    }, follow_redirects=False)
    assert r1.status_code == 303
    c1 = r1.cookies.get(server.SESSION_COOKIE)

    r2 = client.post("/register", data={
        "username": "Rytir_CZ",
        "password": "password456",
        "password_confirm": "password456"
    }, follow_redirects=False)
    assert r2.status_code == 303
    c2 = r2.cookies.get(server.SESSION_COOKIE)

    # 3. Free For All (FFA)
    client.cookies.set(server.SESSION_COOKIE, c1)
    ffa_start = client.post("/api/ffa/start", json={"count": 5})
    assert ffa_start.status_code == 200
    assert ffa_start.json()["mode"] == "ffa"
    ffa_sub1 = client.post("/api/ffa/submit", json={"correct_count": 7, "total_questions": 10, "time_ms": 20000}).json()
    assert ffa_sub1["rank"] == 1 and ffa_sub1["is_leader"] is True

    client.cookies.set(server.SESSION_COOKIE, c2)
    ffa_sub2 = client.post("/api/ffa/submit", json={"correct_count": 9, "total_questions": 10, "time_ms": 18000}).json()
    assert ffa_sub2["rank"] == 1 and ffa_sub2["is_leader"] is True

    # 4. 1v1 Duel (Hráč 1 založí výzvu, Hráč 2 ji přijme a vyhraje)
    client.cookies.set(server.SESSION_COOKIE, c1)
    duel_start1 = client.post("/api/duel/start", json={"count": 5}).json()
    q_ids = [q["id"] for q in duel_start1["questions"]]
    duel_sub1 = client.post("/api/duel/submit", json={
        "correct_count": 5,
        "total_questions": 5,
        "time_ms": 40000,
        "answers": [{"id": qid, "isCorrect": True} for qid in q_ids[:3]] + [{"id": qid, "isCorrect": False} for qid in q_ids[3:]]
    }).json()
    assert duel_sub1["resolved"] is False
    duel_id = duel_sub1["duel_id"]

    client.cookies.set(server.SESSION_COOKIE, c2)
    duel_start2 = client.post("/api/duel/start", json={"duel_id": duel_id}).json()
    assert duel_start2["duel"]["id"] == duel_id
    duel_sub2 = client.post("/api/duel/submit", json={
        "duel_id": duel_id,
        "correct_count": 5,
        "total_questions": 5,
        "time_ms": 15000,
        "explicit_score": 999
    }).json()
    assert duel_sub2["resolved"] is True
    assert duel_sub2["won_duel"] is True
    assert duel_sub2["winner_username"] == "Rytir_CZ"

    # 5. Souhrnný endpoint /api/competitive/overview
    ov = client.get("/api/competitive/overview").json()
    assert "ffa" in ov and "duel" in ov and "koth" in ov
    assert ov["ffa"]["leader"]["username"] == "Rytir_CZ"
    assert len(ov["duel"]["recent_duels"]) == 1


def test_r7_competitive_rooms_lobby_and_host_start(temp_env):
    """R7: Ověření kompetitivních místností (Rooms v lobby) – vytvoření, čekání na hráče, spuštění 👑 hostitelem i auto-start 1v1."""
    client = temp_env

    # Zaregistrovat 2 hráče
    r1 = client.post("/register", data={"username": "HostKing", "password": "pw123456", "password_confirm": "pw123456"}, follow_redirects=False)
    c1 = r1.cookies.get(server.SESSION_COOKIE)
    r2 = client.post("/register", data={"username": "ChallengerTwo", "password": "pw123456", "password_confirm": "pw123456"}, follow_redirects=False)
    c2 = r2.cookies.get(server.SESSION_COOKIE)

    # 1. HostKing vytvoří FFA místnost
    client.cookies.set(server.SESSION_COOKIE, c1)
    cr = client.post("/api/rooms/create", json={"mode": "ffa", "name": "Večerní TZI Aréna", "count": 5}).json()
    assert cr["ok"] is True
    room_id = cr["room"]["id"]
    assert cr["room"]["status"] == "waiting"
    assert cr["room"]["host_username"] == "HostKing"
    assert cr["room"]["player_count"] == 1

    # 2. ChallengerTwo vidí místnost v lobby a připojí se
    client.cookies.set(server.SESSION_COOKIE, c2)
    rooms_list = client.get("/api/rooms").json()
    assert any(r["id"] == room_id for r in rooms_list["active_rooms"])

    join_res = client.post(f"/api/rooms/{room_id}/join", json={"auto_start_duel": False}).json()
    assert join_res["ok"] is True
    assert join_res["room"]["player_count"] == 2
    assert join_res["room"]["status"] == "waiting"

    # ChallengerTwo (není 👑 host) nemůže hru odstartovat
    bad_start = client.post(f"/api/rooms/{room_id}/start")
    assert bad_start.status_code == 403

    # 3. HostKing (👑) odstartuje místnost
    client.cookies.set(server.SESSION_COOKIE, c1)
    start_res = client.post(f"/api/rooms/{room_id}/start")
    assert start_res.status_code == 200
    started_data = start_res.json()
    assert started_data["room"]["status"] == "in_progress"
    assert len(started_data["questions"]) == 5

    # 4. Oba hráči odešlou výsledky v místnosti
    sub1 = client.post(f"/api/rooms/{room_id}/submit", json={"correct_count": 3, "total_questions": 5, "time_ms": 25000}).json()
    assert sub1["ok"] is True
    assert sub1["room"]["status"] == "in_progress"  # Čeká na druhého hráče

    client.cookies.set(server.SESSION_COOKIE, c2)
    sub2 = client.post(f"/api/rooms/{room_id}/submit", json={"correct_count": 5, "total_questions": 5, "time_ms": 15000}).json()
    assert sub2["ok"] is True
    assert sub2["room"]["status"] == "completed"
    assert sub2["room"]["winner_username"] == "ChallengerTwo"
    assert sub2["rank"] == 1

    # 5. Test 1v1 Duel místnosti s auto-startem po připojení 2. hráče
    client.cookies.set(server.SESSION_COOKIE, c1)
    duel_room = client.post("/api/rooms/create", json={"mode": "duel", "name": "Rychlé 1v1", "count": 5}).json()["room"]
    assert duel_room["status"] == "waiting" and duel_room["max_players"] == 2

    client.cookies.set(server.SESSION_COOKIE, c2)
    duel_join = client.post(f"/api/rooms/{duel_room['id']}/join", json={"auto_start_duel": True}).json()
    assert duel_join["room"]["status"] == "in_progress"
    assert len(duel_join["questions"]) == 5


def test_r8_profile_recap_leaderboard_and_revalidation(temp_env):
    """R8: Ověření subpage Kompetitivní aréna, Profil + Recap, Žebříček a revalidace při mazání dat."""
    client = temp_env
    novy_html = (BASE / "ui" / "novy.html").read_text(encoding="utf-8")
    assert 'id="comp-arena"' in novy_html
    assert 'id="profile-view"' in novy_html
    assert 'id="leaderboard-view"' in novy_html
    assert 'id="revalidate-modal"' in novy_html
    assert "WASM_CORE.exp.calcAchievementMask" in novy_html
    assert "WASM_CORE.exp.calcRecapAccuracy" in novy_html

    r = client.post("/register", data={"username": "StudentRecap", "password": "secret123", "password_confirm": "secret123"}, follow_redirects=False)
    assert r.status_code == 303
    client.cookies.set(server.SESSION_COOKIE, r.cookies.get(server.SESSION_COOKIE))

    # Recap endpoint
    recap = client.get("/api/account/recap").json()
    assert recap["username"] == "StudentRecap"
    assert isinstance(recap["sources"], list) and len(recap["sources"]) > 0

    # Leaderboard endpoint s plným žebříčkem
    lb = client.get("/api/leaderboard").json()
    assert "leaderboard" in lb and isinstance(lb["leaderboard"], list)

    # Revalidace před smazáním dat - špatné heslo musí vrátit 403
    bad_del = client.post("/api/account/revalidate-delete", json={"password": "wrongpassword", "scope": "source", "source": "01-2026-10-01"})
    assert bad_del.status_code == 403

    # Revalidace se správným heslem projde
    ok_del = client.post("/api/account/revalidate-delete", json={"password": "secret123", "scope": "source", "source": "01-2026-10-01"})
    assert ok_del.status_code == 200 and ok_del.json()["ok"] is True

    # Změna přezdívky
    u_res = client.post("/api/account/username", json={"username": "StudentMaster"})
    assert u_res.status_code == 200 and u_res.json()["username"] == "StudentMaster"


def test_r9_delete_profile_removes_account(temp_env):
    """R9: Smazání profilu (delete-profile) odstraní uživatele i jeho odpovědi; špatné heslo vrátí 403."""
    client = temp_env
    r = client.post("/register", data={"username": "test123", "password": "heslo1234", "password_confirm": "heslo1234"}, follow_redirects=False)
    assert r.status_code == 303
    client.cookies.set(server.SESSION_COOKIE, r.cookies.get(server.SESSION_COOKIE))
    uid = db.authenticate_user("test123", "heslo1234")["id"]
    scoring.record_question_answer(uid, "1-1", True)

    payload = {"step1_ack": True, "confirm_username": "test123", "confirm_phrase": "DELETE", "password": "spatne"}
    assert client.post("/api/account/delete-profile", json=payload).status_code == 403

    payload["password"] = "heslo1234"
    res = client.post("/api/account/delete-profile", json=payload)
    assert res.status_code == 200 and res.json()["ok"] is True

    conn = db.get_db()
    assert conn.execute("SELECT COUNT(*) FROM users WHERE id = ?", (uid,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM user_answers WHERE user_id = ?", (uid,)).fetchone()[0] == 0
    assert db.authenticate_user("test123", "heslo1234") is None
