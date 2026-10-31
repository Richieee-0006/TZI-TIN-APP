"""
Adversarial empirical challenge harness for Competitive APIs (R3, R4, R5, R6) and UI (R1).
Challenger: teamwork_challenger_tzi_2
"""
import inspect
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import server
import db
import scoring
from webapp import questions

BASE = Path(__file__).resolve().parent.parent


def _cleanup_db(db_path: Path):
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass
    wal = db_path.with_name(db_path.name + "-wal")
    shm = db_path.with_name(db_path.name + "-shm")
    if wal.exists():
        try:
            wal.unlink()
        except OSError:
            pass
    if shm.exists():
        try:
            shm.unlink()
        except OSError:
            pass


def _create_authenticated_client(db_name: str, username_prefix: str = "challenger"):
    test_db = BASE / db_name
    db.close_db()
    _cleanup_db(test_db)
    db.DB_FILE = test_db
    db.init_db()

    ok, err, user = db.register_user(
        theme="games",
        password="AdversarialPassword123!",
        username=f"{username_prefix}_user"
    )
    assert ok and user is not None, f"Failed to register test user: {err}"

    client = TestClient(server.app)
    token = server.create_session_token(user)
    client.cookies.set(server.SESSION_COOKIE, token)
    return client, user, test_db


def test_adversarial_r3_koth_exploit():
    """
    R3 KotH Exploit Verification:
    - Attempt submitting {"correct_count": 10} without answers -> HTTP 400
    - Attempt submitting {"score": 99999} without answers -> HTTP 400
    - Attempt submitting {"correct_count": 10, "score": 99999} without answers -> HTTP 400
    - Attempt submitting empty answers -> HTTP 400
    - Attempt submitting non-list answers -> HTTP 400
    - Attempt submitting spoofed isCorrect without userKeys -> score == 0
    - Legitimate answer -> HTTP 200, score > 0
    """
    client, user, test_db = _create_authenticated_client("test_adv_koth.db")
    try:
        # Attack 1: correct_count without answers
        r1 = client.post("/api/koth/submit", json={"correct_count": 10, "time_ms": 10000})
        assert r1.status_code == 400
        assert "Pole answers je povinné." in r1.json()["detail"]

        # Attack 2: score without answers
        r2 = client.post("/api/koth/submit", json={"score": 99999, "time_ms": 10000})
        assert r2.status_code == 400
        assert "Pole answers je povinné." in r2.json()["detail"]

        # Attack 3: both correct_count and score without answers
        r3 = client.post("/api/koth/submit", json={"correct_count": 10, "score": 99999, "time_ms": 10000})
        assert r3.status_code == 400
        assert "Pole answers je povinné." in r3.json()["detail"]

        # Attack 4: empty answers array
        r4 = client.post("/api/koth/submit", json={"answers": [], "time_ms": 10000})
        assert r4.status_code == 400
        assert "Pole answers je povinné." in r4.json()["detail"]

        # Attack 5: answers not a list
        r5 = client.post("/api/koth/submit", json={"answers": "invalid_string", "time_ms": 10000})
        assert r5.status_code == 400
        assert "Pole answers je povinné." in r5.json()["detail"]

        # Attack 6: spoofed isCorrect=True without userKeys/user_answer
        st = client.post("/api/koth/start").json()
        token = st["match_token"]
        q = st["questions"][0]

        r6 = client.post("/api/koth/submit", json={
            "match_token": token,
            "answers": [{"id": q["id"], "isCorrect": True}],
            "time_ms": 10000
        })
        assert r6.status_code == 200
        assert r6.json()["challenger_score"] == 0

        # Legitimate submission
        st_legit = client.post("/api/koth/start").json()
        token_legit = st_legit["match_token"]
        q_legit = st_legit["questions"][0]
        u_ans = list(q_legit.get("correct", [])) if q_legit.get("type", "choice") == "choice" else q_legit.get("answer", "ok")
        r_valid = client.post("/api/koth/submit", json={
            "match_token": token_legit,
            "answers": [{"id": q_legit["id"], "userKeys": u_ans}],
            "time_ms": 10000
        })
        assert r_valid.status_code == 200
        assert r_valid.json()["challenger_score"] > 0
    finally:
        db.close_db()
        _cleanup_db(test_db)


def test_adversarial_r4_multiplayer_score_spoofing():
    """
    R4 Multiplayer Score Anti-Spoofing:
    - Verify explicit_score is absent from submit_comp_room_result signature
    - Create room and attempt submitting explicit_score: 99999
    - Verify server strictly calculates score from answers & time, ignoring explicit_score
    - Check room database record
    """
    # 1. Signature check
    sig = inspect.signature(scoring.submit_comp_room_result)
    assert "explicit_score" not in sig.parameters

    client, user, test_db = _create_authenticated_client("test_adv_rooms.db")
    try:
        # Create and start room
        c_room = client.post("/api/rooms/create", json={"mode": "ffa", "name": "Adversarial Room", "count": 5})
        assert c_room.status_code == 200
        room_id = c_room.json()["room"]["id"]
        r_start = client.post(f"/api/rooms/{room_id}/start")
        assert r_start.status_code == 200

        # Select 1 valid question
        q = list(questions.ALL_QUESTIONS.values())[0]
        u_ans = list(q.get("correct", [])) if q.get("type", "choice") == "choice" else q.get("answer", "ok")

        # Attempt submitting explicit_score: 99999 and score: 99999
        # Server formula: 1 correct * 100 + max(0, 120 - (10000 // 1000)) = 100 + 110 = 210
        sub_resp = client.post(f"/api/rooms/{room_id}/submit", json={
            "explicit_score": 99999,
            "score": 99999,
            "answers": [{"id": q["id"], "userKeys": u_ans}],
            "time_ms": 10000,
        })
        assert sub_resp.status_code == 200
        resp_data = sub_resp.json()
        assert resp_data["score"] == 210
        assert resp_data["score"] != 99999

        # Verify DB directly
        conn = db.get_db()
        row = conn.execute("SELECT score FROM comp_room_players WHERE room_id = ?", (room_id,)).fetchone()
        assert row is not None
        assert row["score"] == 210
        assert row["score"] != 99999
    finally:
        db.close_db()
        _cleanup_db(test_db)


def test_adversarial_r5_self_duel():
    """
    R5 Self-Duel Prevention:
    - Attempt self-duel with opponent_id == current_user.id -> HTTP 400 'Nelze vyzvat sám sebe.'
    - Attempt joining own open duel via duel_id -> HTTP 400 'Nelze vyzvat sám sebe.'
    """
    client, user, test_db = _create_authenticated_client("test_adv_duel.db")
    try:
        me_resp = client.get("/api/me")
        assert me_resp.status_code == 200
        my_id = me_resp.json()["user_id"]

        # 1. Direct challenge with opponent_id == my_id
        r_self = client.post("/api/duel/start", json={"opponent_id": my_id})
        assert r_self.status_code == 400
        assert r_self.json()["detail"] == "Nelze vyzvat sám sebe."

        # 2. Stringified opponent_id == my_id
        r_self_str = client.post("/api/duel/start", json={"opponent_id": str(my_id)})
        assert r_self_str.status_code == 400
        assert r_self_str.json()["detail"] == "Nelze vyzvat sám sebe."

        # 3. Create open duel, submit run, and attempt joining own duel
        d_start = client.post("/api/duel/start", json={"count": 5}).json()
        token = d_start["match_token"]
        q = d_start["questions"][0]
        u_ans = list(q.get("correct", [])) if q.get("type", "choice") == "choice" else q.get("answer", "ok")
        sub_run = client.post("/api/duel/submit", json={
            "match_token": token,
            "answers": [{"id": q["id"], "userKeys": u_ans}],
            "time_ms": 10000,
        })
        assert sub_run.status_code == 200
        duel_id = sub_run.json()["duel_id"]

        # Attempt joining own duel
        r_join_own = client.post("/api/duel/start", json={"duel_id": duel_id})
        assert r_join_own.status_code == 400
        assert r_join_own.json()["detail"] == "Nelze vyzvat sám sebe."
    finally:
        db.close_db()
        _cleanup_db(test_db)


def test_adversarial_r6_ffa_time_and_answers():
    """
    R6 FFA Anti-speedhack and Answer Validation:
    - time_ms = 4999 -> HTTP 400
    - time_ms = 0 -> HTTP 400
    - time_ms = -100 -> HTTP 400
    - missing answers -> HTTP 400
    - empty answers -> HTTP 400
    - time_ms = 5000 (boundary) -> HTTP 200
    """
    client, user, test_db = _create_authenticated_client("test_adv_ffa.db")
    try:
        ffa_st = client.post("/api/ffa/start").json()
        token = ffa_st["match_token"]
        q = ffa_st["questions"][0]
        u_ans = list(q.get("correct", [])) if q.get("type", "choice") == "choice" else q.get("answer", "ok")
        valid_answers = [{"id": q["id"], "userKeys": u_ans}]

        # 1. Missing answers
        r_no_ans = client.post("/api/ffa/submit", json={"match_token": token, "correct_count": 5, "time_ms": 10000})
        assert r_no_ans.status_code == 400
        assert "Pole answers je povinné." in r_no_ans.json()["detail"]

        # 2. Empty answers
        r_empty = client.post("/api/ffa/submit", json={"match_token": token, "answers": [], "time_ms": 10000})
        assert r_empty.status_code == 400
        assert "Pole answers je povinné." in r_empty.json()["detail"]

        # 3. Speedhack time_ms = 4999
        r_4999 = client.post("/api/ffa/submit", json={"match_token": token, "answers": valid_answers, "time_ms": 4999})
        assert r_4999.status_code == 400
        assert "Čas dokončení je příliš krátký (minimálně 5 sekund)." in r_4999.json()["detail"]

        # 4. Zero time_ms = 0
        r_zero = client.post("/api/ffa/submit", json={"match_token": token, "answers": valid_answers, "time_ms": 0})
        assert r_zero.status_code == 400
        assert "Čas dokončení je příliš krátký (minimálně 5 sekund)." in r_zero.json()["detail"]

        # 5. Negative time_ms = -100
        r_neg = client.post("/api/ffa/submit", json={"match_token": token, "answers": valid_answers, "time_ms": -100})
        assert r_neg.status_code == 400
        assert "Čas dokončení je příliš krátký (minimálně 5 sekund)." in r_neg.json()["detail"]

        # 6. Valid boundary time_ms = 5000 (with fresh token)
        ffa_st2 = client.post("/api/ffa/start").json()
        token2 = ffa_st2["match_token"]
        q2 = ffa_st2["questions"][0]
        u_ans2 = list(q2.get("correct", [])) if q2.get("type", "choice") == "choice" else q2.get("answer", "ok")
        r_5000 = client.post("/api/ffa/submit", json={"match_token": token2, "answers": [{"id": q2["id"], "userKeys": u_ans2}], "time_ms": 5000})
        assert r_5000.status_code == 200
        assert r_5000.json()["score"] > 0
    finally:
        db.close_db()
        _cleanup_db(test_db)


def test_adversarial_r1_ui_single_choice_radio_switch():
    """
    R1 UI single-choice radio switch in ui/js/quiz.js:
    Execute Node.js runner to simulate toggleOpt under single-choice and multi-choice conditions.
    """
    script = r"""
    const fs = require('fs');
    const path = require('path');
    const vm = require('vm');
    const assert = require('assert');

    const quizJsCode = fs.readFileSync(path.join(__dirname, '..', 'ui', 'js', 'quiz.js'), 'utf8');

    const elements = {};
    function mockElement(id) {
        if (!elements[id]) {
            const classes = new Set();
            elements[id] = {
                id,
                classList: {
                    add: (c) => classes.add(c),
                    remove: (c) => classes.delete(c),
                    contains: (c) => classes.has(c),
                }
            };
        }
        return elements[id];
    }

    const context = {
        $: mockElement,
        selected: new Set(),
        queue: [{ correct: ['A'], type: 'choice' }],
        idx: 0,
        checked: false,
        studyMode: false,
        isInput: () => false,
        syncAction: () => {},
    };

    vm.createContext(context);
    const toggleOptMatch = quizJsCode.match(/function toggleOpt\(letter\)[\s\S]*?\n\}/);
    assert(toggleOptMatch, 'toggleOpt found in ui/js/quiz.js');
    vm.runInContext(toggleOptMatch[0], context);

    // 1. Single choice test: select A
    context.toggleOpt('A');
    assert.strictEqual(context.selected.size, 1, 'Should have 1 option selected');
    assert(context.selected.has('A'), 'Option A must be selected');
    assert(context.$('opt-A').classList.contains('selected'), 'opt-A should have class selected');

    // 2. Single choice test: switch to B
    context.toggleOpt('B');
    assert.strictEqual(context.selected.size, 1, 'Should still have exactly 1 option selected after switch');
    assert(!context.selected.has('A'), 'Option A must be unselected');
    assert(context.selected.has('B'), 'Option B must be selected');
    assert(!context.$('opt-A').classList.contains('selected'), 'opt-A must not have class selected');
    assert(context.$('opt-B').classList.contains('selected'), 'opt-B must have class selected');

    // 3. Single choice test: switch to C
    context.toggleOpt('C');
    assert.strictEqual(context.selected.size, 1);
    assert(!context.selected.has('B'));
    assert(context.selected.has('C'));
    assert(!context.$('opt-B').classList.contains('selected'));
    assert(context.$('opt-C').classList.contains('selected'));

    // 4. Single choice test: toggle C off
    context.toggleOpt('C');
    assert.strictEqual(context.selected.size, 0, 'Clicking selected option unselects it');
    assert(!context.selected.has('C'));
    assert(!context.$('opt-C').classList.contains('selected'));

    // 5. Multi choice test: correct = ['A', 'B']
    context.queue[0] = { correct: ['A', 'B'], type: 'choice' };
    context.selected.clear();
    context.toggleOpt('A');
    context.toggleOpt('B');
    assert.strictEqual(context.selected.size, 2);
    assert(context.selected.has('A') && context.selected.has('B'));

    // Multi choice: click C when full -> blocked
    context.toggleOpt('C');
    assert.strictEqual(context.selected.size, 2, 'Option C should be blocked in multi-choice when limit reached');
    assert(!context.selected.has('C'));

    // Unselect A and select C
    context.toggleOpt('A');
    assert.strictEqual(context.selected.size, 1);
    context.toggleOpt('C');
    assert.strictEqual(context.selected.size, 2);
    assert(context.selected.has('B') && context.selected.has('C'));

    console.log('UI radio button test PASSED');
    """;

    res = subprocess.run(["node", "-e", script], cwd=str(BASE / "tests"), capture_output=True, text=True)
    assert res.returncode == 0, f"Node test failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert "UI radio button test PASSED" in res.stdout


def test_adversarial_match_session_token_and_replay_defense():
    """
    Match session authorization & replay defense:
    - Starting a competitive match returns a cryptographically signed match_token.
    - Token replay is rejected with HTTP 400.
    - Submitting questions not in token question list is rejected with HTTP 400.
    - Tampered token signature is rejected with HTTP 400.
    """
    client, user, test_db = _create_authenticated_client("test_adv_match_token.db")
    try:
        # Start KotH
        res = client.post("/api/koth/start")
        assert res.status_code == 200
        data = res.json()
        assert "match_token" in data
        token = data["match_token"]
        qs = data["questions"]
        assert len(qs) > 0
        q = qs[0]
        u_ans = list(q.get("correct", [])) if q.get("type", "choice") == "choice" else q.get("answer", "ok")

        # 1. Valid submit with token
        sub_res = client.post("/api/koth/submit", json={
            "match_token": token,
            "answers": [{"id": q["id"], "userKeys": u_ans}],
            "time_ms": 10000
        })
        assert sub_res.status_code == 200

        # 2. Replay with same token rejected
        replay_res = client.post("/api/koth/submit", json={
            "match_token": token,
            "answers": [{"id": q["id"], "userKeys": u_ans}],
            "time_ms": 10000
        })
        assert replay_res.status_code == 400
        assert "opakované použití" in replay_res.json()["detail"]

        # 3. Mismatched question in token rejected
        res2 = client.post("/api/koth/start")
        token2 = res2.json()["match_token"]
        bad_q_res = client.post("/api/koth/submit", json={
            "match_token": token2,
            "answers": [{"id": "fake_q_9999", "userKeys": "A"}],
            "time_ms": 10000
        })
        assert bad_q_res.status_code == 400
        assert "nebyla pro tento zápas vygenerována" in bad_q_res.json()["detail"]

        # 4. Tampered token rejected
        tampered_token = token2[:-4] + "xxxx"
        tampered_res = client.post("/api/koth/submit", json={
            "match_token": tampered_token,
            "answers": [{"id": q["id"], "userKeys": u_ans}],
            "time_ms": 10000
        })
        assert tampered_res.status_code == 400
        assert "Neplatný podpis" in tampered_res.json()["detail"]
    finally:
        db.close_db()
        _cleanup_db(test_db)
