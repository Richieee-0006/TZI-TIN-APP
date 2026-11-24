"""Graceful Deprecation Bridge Mode for migrating standalone tzi.rutterle.eu to uni.rutterle.eu.

Controlled via environment variables (all OFF by default so standalone mode is unchanged):
- UNI_MIGRATION_MODE=1: shows steel-blue migration banner & redirects /register to uni.rutterle.eu
- UNI_TRIAL_ONLY=1: disables local DB logins/registrations (Trial-only mode)
- UNI_TARGET_URL: destination subject URL (default https://uni.rutterle.eu/predmet/tzi)
- UNI_REGISTER_URL: destination register URL (default https://uni.rutterle.eu/register?from=tzi)
- UNI_INTERNAL_BUNDLE_URL: loopback-only URL (http://127.0.0.1:5052/internal/subjects/tzi/bundle)
- INTERNAL_SYNC_TOKEN: shared loopback sync token
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from .config import BASE

_log = logging.getLogger(__name__)
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.json$")
_BODY_OPEN_RE = re.compile(r"(<body\b[^>]*>)", re.IGNORECASE)
_HEAD_CLOSE_RE = re.compile(r"(</head>)", re.IGNORECASE)


def is_migration_mode() -> bool:
    return os.environ.get("UNI_MIGRATION_MODE", "0").strip() == "1"


def is_trial_only() -> bool:
    return os.environ.get("UNI_TRIAL_ONLY", "0").strip() == "1"


def get_target_url() -> str:
    raw = os.environ.get("UNI_TARGET_URL", "https://uni.rutterle.eu/predmet/tzi").strip()
    parsed = urlparse(raw)
    if parsed.scheme in ("https", "http") and parsed.netloc:
        return raw
    return "https://uni.rutterle.eu/predmet/tzi"


def get_register_url() -> str:
    raw = os.environ.get("UNI_REGISTER_URL", "https://uni.rutterle.eu/register?from=tzi").strip()
    parsed = urlparse(raw)
    if parsed.scheme in ("https", "http") and parsed.netloc:
        return raw
    return "https://uni.rutterle.eu/register?from=tzi"


def get_bundle_url() -> str:
    return os.environ.get("UNI_INTERNAL_BUNDLE_URL", "").strip()


def get_sync_token() -> str:
    return os.environ.get("INTERNAL_SYNC_TOKEN", "").strip()


def _is_loopback_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")


def inject_deprecation_banner(html: str) -> str:
    """Inject CSP-safe steel-blue migration banner & stylesheet when UNI_MIGRATION_MODE=1."""
    if not is_migration_mode() or "uni-bridge-banner" in html:
        return html

    target = escape(get_target_url(), quote=True)
    css_link = '<link rel="stylesheet" href="/static/css/uni-bridge.css">'
    banner = (
        '<aside class="uni-bridge-banner" aria-label="Přesun na UNI Suite">'
        '<div class="uni-bridge-inner">'
        '<p class="uni-bridge-text">'
        "TZI Trenér se přesunul na uni.rutterle.eu — účet, postup i nové předměty najdeš na jednom místě."
        "</p>"
        f'<a class="uni-bridge-cta" href="{target}">Přejít na UNI <span aria-hidden="true">→</span></a>'
        "</div>"
        "</aside>"
    )

    out = _HEAD_CLOSE_RE.sub(f"{css_link}\\1", html, count=1)
    out = _BODY_OPEN_RE.sub(f"\\1{banner}", out, count=1)
    return out


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def pull_tzi_bundle(timeout: int = 10) -> tuple[bool, str]:
    """Pull TZI banks & glossary from loopback uni-suite bundle endpoint."""
    url = get_bundle_url()
    token = get_sync_token()
    if not url or not token:
        return False, "Bridge sync není nakonfigurován."
    if not _is_loopback_url(url):
        _log.warning("Refusing non-loopback UNI_INTERNAL_BUNDLE_URL: %s", url)
        return False, "UNI_INTERNAL_BUNDLE_URL musí směřovat na loopback (127.0.0.1 / ::1)."

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path, headers={"X-Internal-Token": token, "Accept": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            return False, f"HTTP {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _log.warning("Bridge bundle pull failed: %s", exc)
        return False, str(exc)
    finally:
        conn.close()

    written = 0
    banky_dir = BASE / "banky"
    dopl_dir = banky_dir / "doplnovacka"
    glosar_dir = BASE / "glosar"

    for fname, content in (data.get("banks") or {}).items():
        if _SAFE_NAME_RE.match(fname) and isinstance(content, dict):
            _atomic_write_json(banky_dir / fname, content)
            written += 1

    for fname, content in (data.get("recall_banks") or {}).items():
        if _SAFE_NAME_RE.match(fname) and isinstance(content, dict):
            _atomic_write_json(dopl_dir / fname, content)
            written += 1

    glossary = data.get("glossary")
    if isinstance(glossary, dict) and glossary:
        _atomic_write_json(glosar_dir / "glosar.json", glossary)
        written += 1

    return True, f"Synchronizováno {written} souborů z UNI Suite."
