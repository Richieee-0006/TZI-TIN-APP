"""
Adversarial empirical challenge harness for Study & System APIs (R2, R7, R8).
Challenger: teamwork_challenger_tzi_1
"""
import time
import secrets
from pathlib import Path
from fastapi.testclient import TestClient

import server
import db
import scoring
from webapp import questions
from webapp.routers import study, pwa

BASE = Path(__file__).resolve().parent.parent


def _cleanup_db(db_path: Path):
    db.close_db()
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
    db.close_db()


def _setup_client_with_user(db_name="test_challenger.db"):
    test_db = BASE / db_name
    _cleanup_db(test_db)
    db.DB_FILE = test_db
    db.init_db()

    client = TestClient(server.app)
    r_reg = client.get("/register")
    csrf_token = r_reg.cookies.get("csrf_token")
    reg_resp = client.post(
        "/register",
        data={
            "theme": "games",
            "password": "adversarial_pwd_456",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    cookie = reg_resp.cookies.get(server.SESSION_COOKIE)
    client.cookies.set(server.SESSION_COOKIE, cookie)
    return client, test_db


def test_adversarial_r2_progress_spoofing():
    """Adversarial Attack 1: Stress test /api/progress anti-spoofing and rejection of malicious payloads."""
    client, test_db = _setup_client_with_user("test_challenger_r2.db")
    try:
        s_resp = client.get("/api/sources")
        assert s_resp.status_code == 200
        sources = s_resp.json()["sources"]
        assert len(sources) > 0
        src = sources[0]["id"]

        q_resp = client.get(f"/api/questions?source={src}")
        assert q_resp.status_code == 200
        q_list = q_resp.json()
        assert len(q_list) > 0
        q = q_list[0]
        q_id = q["id"]
        correct_ans = q.get("correct") or q.get("answer")

        # 1. Spoof attempt: isCorrect=True without userKeys or user_answer
        spoof_payloads_missing_keys = [
            {"seen": {}, "latest": {"id": q_id, "isCorrect": True}},
            {"seen": {}, "latest": {"id": q_id, "isCorrect": True, "points": 9999}},
            {"seen": {}, "latest": {"id": q_id, "isCorrect": True, "userKeys": None}},
            {"seen": {}, "latest": {"id": q_id, "isCorrect": True, "user_answer": None}},
            {"seen": {}, "latest": {"id": q_id, "isCorrect": "true"}},
        ]
        for p in spoof_payloads_missing_keys:
            r = client.post(f"/api/progress?source={src}", json=p)
            assert r.status_code == 400, f"Expected 400 for payload {p}, got {r.status_code}"
            assert "userKeys" in r.json().get("detail", "") or "user_answer" in r.json().get("detail", "")

        # 2. Spoof attempt: Malformed 'latest' structure or nonexistent question IDs
        malformed_latest_payloads = [
            {"seen": {}, "latest": {"userKeys": ["A"]}},  # missing id
            {"seen": {}, "latest": {"id": "", "userKeys": ["A"]}},  # empty id
            {"seen": {}, "latest": {"id": "nonexistent_q_999999", "userKeys": ["A"]}},  # unknown question
            {"seen": {}, "latest": {"id": "sql_inject' OR 1=1 --", "userKeys": ["A"]}},  # malicious string
            {"seen": {}, "latest": "string_not_dict"},  # invalid type
            {"seen": {}, "latest": 12345},  # invalid type
        ]
        for p in malformed_latest_payloads:
            r = client.post(f"/api/progress?source={src}", json=p)
            assert r.status_code == 400, f"Expected 400 for malformed payload {p}, got {r.status_code}"

        # 3. Spoof attempt: Invalid keys with isCorrect=True claim
        adversarial_invalid_answers = [
            ["WRONG_CHOICE_XYZ"],
            ["A", "B", "C", "D", "E"],  # all choices selected
            [],  # empty selection
            ["__proto__"],  # prototype pollution probe
            "WRONG_STRING_VALUE",
            {"fake": "obj"},
        ]
        for bad_ans in adversarial_invalid_answers:
            r = client.post(
                f"/api/progress?source={src}",
                json={
                    "seen": {},
                    "session": None,
                    "latest": {"id": q_id, "userKeys": bad_ans, "isCorrect": True, "score": 100},
                },
            )
            assert r.status_code == 200, f"Request with answer {bad_ans} failed with status {r.status_code}"
            data = r.json()
            assert data["ok"] is True
            assert data["score"] is not None
            assert data["score"]["points_awarded"] == 0, f"Points awarded > 0 for fake answer {bad_ans}"
            conn = db.get_db()
            last_ans = conn.execute(
                "SELECT is_correct, points_awarded FROM user_answers WHERE user_id = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert last_ans["is_correct"] == 0
            assert last_ans["points_awarded"] == 0

        # 4. Legitimate verification: authentic correct answer on a fresh question awards points (attempt 1 -> 3 base points)
        assert len(q_list) > 1, "Expected at least 2 questions in test dataset"
        fresh_q = q_list[1]
        fresh_id = fresh_q["id"]
        fresh_correct = fresh_q.get("correct") or fresh_q.get("answer")

        r_legit = client.post(
            f"/api/progress?source={src}",
            json={
                "seen": {fresh_id: "correct"},
                "session": None,
                "latest": {"id": fresh_id, "userKeys": fresh_correct},
            },
        )
        assert r_legit.status_code == 200
        legit_data = r_legit.json()
        assert legit_data["score"]["points_awarded"] > 0, "Legitimate answer on first attempt must award points"
        points_earned = legit_data["score"]["points_awarded"]

        # 5. Database score verification: verify DB has only legitimate points
        conn = db.get_db()
        score_row = conn.execute("SELECT total_points FROM user_scores WHERE user_id = 1").fetchone()
        assert score_row["total_points"] == points_earned, f"User score {score_row['total_points']} does not match earned {points_earned}"

    finally:
        _cleanup_db(test_db)


def test_adversarial_r7_client_error_flooding():
    """Adversarial Attack 2: 50 rapid error requests from single IP -> HTTP 429 after 10 requests, exactly 10 DB writes."""
    study.reset_client_error_rate_limits()
    test_db = BASE / "test_challenger_r7.db"
    _cleanup_db(test_db)
    db.DB_FILE = test_db
    db.init_db()

    client = TestClient(server.app)
    try:
        results = []
        # Rapidly fire 50 client-error requests
        for i in range(1, 51):
            resp = client.post(
                "/api/client-error",
                json={
                    "message": f"adversarial_flood_payload_{i}",
                    "file": f"exploit_{i}.js",
                    "stack": f"Stack trace line {i}\nError: simulated flood",
                },
            )
            results.append((i, resp.status_code))

        # Check request 1 to 10: 200 OK
        for idx, status in results[:10]:
            assert status == 200, f"Request {idx} expected 200, got {status}"

        # Check request 11 to 50: 429 Too Many Requests
        for idx, status in results[10:]:
            assert status == 429, f"Request {idx} expected 429, got {status}"

        # Check SQLite DB writes: must be exactly 10, zero excess records
        conn = db.get_db()
        cursor = conn.execute("SELECT count(*) as cnt FROM error_logs WHERE level = 'UI_ERROR'")
        db_count = cursor.fetchone()["cnt"]
        assert db_count == 10, f"Expected exactly 10 error records in DB, found {db_count}!"

        # Check that flooded IP remains blocked on 51st attempt
        r_blocked = client.post("/api/client-error", json={"message": "still_flooding"})
        assert r_blocked.status_code == 429

        # Verify rate limit reset restores functionality
        study.reset_client_error_rate_limits()
        r_recovered = client.post("/api/client-error", json={"message": "recovered"})
        assert r_recovered.status_code == 200
        cursor2 = conn.execute("SELECT count(*) as cnt FROM error_logs WHERE level = 'UI_ERROR'")
        assert cursor2.fetchone()["cnt"] == 11

    finally:
        study.reset_client_error_rate_limits()
        _cleanup_db(test_db)


def test_adversarial_r8_webhook_timing_safe_secret(monkeypatch):
    """Adversarial Attack 3: Webhook secret validation with valid/invalid secrets and timing-safe comparison."""
    test_secret = "k3y_W3bh00k_S3cr3t_2026_xYz987!@"
    monkeypatch.setattr(pwa, "WEBHOOK_SECRET", test_secret)
    monkeypatch.setattr(pwa, "git_pull", lambda: "test_git_pull_executed")

    called_pairs = []
    real_compare_digest = secrets.compare_digest

    def spy_compare(a, b):
        called_pairs.append((a, b))
        return real_compare_digest(a, b)

    monkeypatch.setattr(secrets, "compare_digest", spy_compare)

    client = TestClient(server.app)

    # 1. Missing secret
    r_none = client.post("/webhook")
    assert r_none.status_code == 403

    # 2. Empty secret
    r_empty = client.post("/webhook?secret=")
    assert r_empty.status_code == 403

    # 3. Wrong secret of completely different length
    r_short = client.post("/webhook?secret=short")
    assert r_short.status_code == 403

    # 4. Wrong secret matching prefix
    r_prefix = client.post(f"/webhook?secret={test_secret[:-5]}")
    assert r_prefix.status_code == 403

    # 5. Wrong secret identical length with single character flipped at start, middle, and end
    bad_start = ("X" if test_secret[0] != "X" else "Y") + test_secret[1:]
    bad_mid = test_secret[:10] + ("X" if test_secret[10] != "X" else "Y") + test_secret[11:]
    bad_end = test_secret[:-1] + ("X" if test_secret[-1] != "X" else "Y")

    for bad in (bad_start, bad_mid, bad_end):
        r_bad = client.post(f"/webhook?secret={bad}")
        assert r_bad.status_code == 403, f"Secret {bad} should return 403"

    # 6. Valid secret
    r_valid = client.post(f"/webhook?secret={test_secret}")
    assert r_valid.status_code == 200
    assert "test_git_pull_executed" in r_valid.text

    # 7. Verify secrets.compare_digest was called for secret comparisons
    assert len(called_pairs) >= 6
    # Verify that the valid secret call compared test_secret with test_secret
    assert (test_secret, test_secret) in called_pairs


def test_adversarial_r2_sync_batch_spoofing():
    """Adversarial Attack: Batch /api/sync spoofing, duplicate answers, and >100 batch size capping."""
    client, test_db = _setup_client_with_user("test_challenger_sync.db")
    try:
        s_resp = client.get("/api/sources")
        src = s_resp.json()["sources"][0]["id"]
        q_list = client.get(f"/api/questions?source={src}").json()
        assert len(q_list) >= 2
        q1, q2 = q_list[0], q_list[1]
        q1_ans = q1.get("correct") or q1.get("answer")
        q2_ans = q2.get("correct") or q2.get("answer")

        # 1. Batch submission containing spoof attempts, duplicates, nonexistent questions
        batch_payload = {
            "source": src,
            "seen": {},
            "answers": [
                {"id": q1["id"]},  # Missing userKeys / user_answer -> ignored
                {"id": q1["id"], "userKeys": ["DEFINITELY_WRONG_CHOICE"], "isCorrect": True},  # Wrong answer -> 0 points
                {"id": "nonexistent_fake_question_9999", "userKeys": ["A"], "isCorrect": True},  # Nonexistent -> ignored
                {"id": q2["id"], "userKeys": q2_ans},  # Genuine correct answer -> awards points
                {"id": q2["id"], "userKeys": q2_ans},  # Duplicate question in same batch -> deduplicated/ignored
            ]
        }
        r_sync = client.post("/api/sync", json=batch_payload)
        assert r_sync.status_code == 200
        sync_data = r_sync.json()
        assert sync_data["ok"] is True
        # Only valid distinct question IDs with user answer are processed
        assert sync_data["synced_count"] >= 1
        assert sync_data["points_awarded"] > 0

        # Verify in DB: q2 awarded points, q1 0 points, fake nonexistent not in user_answers
        conn = db.get_db()
        q1_rows = conn.execute("SELECT * FROM user_answers WHERE question_id = ?", (q1["id"],)).fetchall()
        for row in q1_rows:
            assert row["is_correct"] == 0
            assert row["points_awarded"] == 0

        fake_rows = conn.execute("SELECT * FROM user_answers WHERE question_id = 'nonexistent_fake_question_9999'").fetchall()
        assert len(fake_rows) == 0, "Nonexistent question should never be logged in user_answers"

        # 2. Oversized batch (>100 answers) capped at 100
        huge_batch = [{"id": f"q_dummy_{i}", "userKeys": ["A"]} for i in range(150)]
        r_huge = client.post("/api/sync", json={"source": src, "seen": {}, "answers": huge_batch})
        assert r_huge.status_code == 200

        # 3. Rate limiting test: spamming /api/sync gets HTTP 429
        rate_limited = False
        for _ in range(15):
            res_spam = client.post("/api/sync", json={"source": src, "seen": {}, "answers": []})
            if res_spam.status_code == 429:
                rate_limited = True
                assert "Rate limit" in res_spam.json()["detail"] or "synchronizačních požadavků" in res_spam.json()["detail"]
                break
        assert rate_limited is True, "Spamming /api/sync must trigger rate limit 429"
        study.reset_sync_rate_limits()

    finally:
        _cleanup_db(test_db)


def test_adversarial_r7_header_spoofing():
    """Adversarial Attack: Attempt bypassing /api/client-error rate limit using spoofed X-Forwarded-For headers."""
    study.reset_client_error_rate_limits()
    test_db = BASE / "test_challenger_spoof_r7.db"
    _cleanup_db(test_db)
    db.DB_FILE = test_db
    db.init_db()

    client = TestClient(server.app)
    try:
        # Exhaust 10 allowed requests
        for i in range(10):
            r = client.post("/api/client-error", json={"message": f"err_{i}"})
            assert r.status_code == 200

        # Attempt to spoof client IP via X-Forwarded-For, X-Real-IP, Forwarded
        spoofed_headers = [
            {"X-Forwarded-For": "198.51.100.1"},
            {"X-Forwarded-For": "203.0.113.195, 10.0.0.1"},
            {"X-Real-IP": "192.0.2.1"},
            {"Forwarded": "for=192.0.2.60;proto=http;by=203.0.113.43"},
        ]
        for headers in spoofed_headers:
            r_spoof = client.post("/api/client-error", json={"message": "spoof_bypass"}, headers=headers)
            # Server relies on request.client.host (socket IP), NOT untrusted client headers
            assert r_spoof.status_code == 429, f"Header spoof {headers} should NOT bypass rate limit!"

        # Verify DB still has exactly 10 error records
        conn = db.get_db()
        cnt = conn.execute("SELECT count(*) as c FROM error_logs WHERE level = 'UI_ERROR'").fetchone()["c"]
        assert cnt == 10

    finally:
        study.reset_client_error_rate_limits()
        _cleanup_db(test_db)
