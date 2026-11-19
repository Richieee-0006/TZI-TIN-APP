"""Automatická synchronizace bank otázek z upstream repozitáře (zdenax/TZI-TIN-APP)."""
import os
import shutil
import subprocess
import time
from .config import BASE
from .questions import refresh_questions


UPSTREAM_URL = "https://github.com/zdenax/TZI-TIN-APP.git"


def _git(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Spustí lokální git s plnou ověřenou cestou a bez shellu."""
    git_bin = shutil.which("git")
    if not git_bin or not os.path.isabs(git_bin):
        raise RuntimeError("git binary not found")
    return subprocess.run([git_bin, *args], cwd=BASE, capture_output=True, text=True, timeout=timeout, shell=False)  # noqa: S603


def _ensure_upstream_remote():
    """Zajistí existenci git remote 'upstream' mířícího na zdenax/TZI-TIN-APP."""
    res = _git("remote", "get-url", "upstream", timeout=15)
    if res.returncode != 0:
        _git("remote", "add", "upstream", UPSTREAM_URL, timeout=15)
    elif UPSTREAM_URL not in res.stdout:
        _git("remote", "set-url", "upstream", UPSTREAM_URL, timeout=15)


# --- Git Auto-sync Worker (pouze banky otázek z upstream/main) ---
def git_pull():
    try:
        _ensure_upstream_remote()
        print("[Auto-sync] Kontroluji nové banky otázek z upstream/main (zdenax/TZI-TIN-APP)...")
        fetch_res = _git("fetch", "upstream", "main", timeout=30)
        if fetch_res.returncode != 0:
            err = (fetch_res.stdout + "\n" + fetch_res.stderr).strip()
            print(f"[Auto-sync] Chyba při git fetch upstream: {err}")
            return err

        checkout_res = _git("checkout", "upstream/main", "--", ":(glob)banky/*.json", "glosar", timeout=30)
        out = (checkout_res.stdout + "\n" + checkout_res.stderr).strip()

        # Okamžitě obnovit cache otázek v paměti běžícího serveru
        refresh_questions()

        # Pokud se v banky/ nebo glosar/ něco změnilo, commitnout a pushnout do vlastního forku (origin)
        status_res = _git("status", "--porcelain", "--", ":(glob)banky/*.json", "glosar", timeout=15)
        if status_res.stdout.strip():
            _git("add", "--", ":(glob)banky/*.json", "glosar", timeout=15)
            _git("commit", "--only", "-m", "chore(banky): auto-sync question banks from upstream/main", "--", ":(glob)banky/*.json", "glosar", timeout=15)
            push_res = _git("push", "origin", "main", timeout=30)
            out = (out + f"\n[Auto-sync] Nové banky uloženy a pushnuty do origin/main ({push_res.returncode}).").strip()
        else:
            out = "Banky otázek jsou aktuální vůči upstream/main."

        print(f"[Auto-sync] Výsledek: {out}")
        return out
    except Exception as e:
        print(f"[Auto-sync] Chyba: {e}")
        return str(e)


def sync_worker():
    while True:
        time.sleep(15 * 60)
        git_pull()
