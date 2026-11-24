"""Tests for Graceful Deprecation Bridge Mode (UNI_MIGRATION_MODE / UNI_TRIAL_ONLY)."""

from __future__ import annotations

import os
from fastapi.testclient import TestClient

os.environ.setdefault("APP_SECRET", "test-secret-key-for-uni-bridge-tests-0123456789")

from webapp.main import app
from webapp import uni_bridge


def test_bridge_disabled_by_default(monkeypatch):
    monkeypatch.delenv("UNI_MIGRATION_MODE", raising=False)
    monkeypatch.delenv("UNI_TRIAL_ONLY", raising=False)
    client = TestClient(app)
    r = client.get("/login")
    assert r.status_code == 200
    assert "uni-bridge-banner" not in r.text
    r_reg = client.get("/register", follow_redirects=False)
    assert r_reg.status_code == 200


def test_migration_mode_banner_and_register_redirect(monkeypatch):
    monkeypatch.setenv("UNI_MIGRATION_MODE", "1")
    monkeypatch.setenv("UNI_TARGET_URL", "https://uni.rutterle.eu/predmet/tzi")
    monkeypatch.setenv("UNI_REGISTER_URL", "https://uni.rutterle.eu/register?from=tzi")
    client = TestClient(app)

    r_login = client.get("/login")
    assert r_login.status_code == 200
    assert "uni-bridge-banner" in r_login.text
    assert "/static/css/uni-bridge.css" in r_login.text
    assert "https://uni.rutterle.eu/predmet/tzi" in r_login.text

    r_reg_get = client.get("/register", follow_redirects=False)
    assert r_reg_get.status_code == 303
    assert r_reg_get.headers["location"] == "https://uni.rutterle.eu/register?from=tzi"

    r_reg_post = client.post(
        "/register",
        data={"username": "novy", "password": "password123"},
        follow_redirects=False,
    )
    assert r_reg_post.status_code == 303
    assert r_reg_post.headers["location"] == "https://uni.rutterle.eu/register?from=tzi"


def test_trial_only_blocks_local_login(monkeypatch):
    monkeypatch.setenv("UNI_MIGRATION_MODE", "1")
    monkeypatch.setenv("UNI_TRIAL_ONLY", "1")
    monkeypatch.setenv("UNI_TARGET_URL", "https://uni.rutterle.eu/predmet/tzi")
    client = TestClient(app)

    r = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "https://uni.rutterle.eu/predmet/tzi"


def test_bundle_pull_rejects_non_loopback(monkeypatch):
    monkeypatch.setenv("UNI_INTERNAL_BUNDLE_URL", "https://evil.example.com/bundle")
    monkeypatch.setenv("INTERNAL_SYNC_TOKEN", "tok123")
    ok, msg = uni_bridge.pull_tzi_bundle()
    assert ok is False
    assert "loopback" in msg
