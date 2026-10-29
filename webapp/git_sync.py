"""Automatická synchronizace bank otázek z upstream repozitáře."""
import time
import subprocess
from .config import BASE
from .questions import refresh_questions


# --- Git Auto-sync Worker (pouze banky otázek z upstreamu) ---
def git_pull():
    try:
        print("[Auto-sync] Kontroluji nové banky otázek z upstream/main...")
        fetch_res = subprocess.run(
            ["git", "fetch", "upstream", "main"],
            cwd=BASE, capture_output=True, text=True, timeout=30
        )
        if fetch_res.returncode != 0:
            err = (fetch_res.stdout + "\n" + fetch_res.stderr).strip()
            print(f"[Auto-sync] Chyba při git fetch upstream: {err}")
            return err

        checkout_res = subprocess.run(
            ["git", "checkout", "upstream/main", "--", "banky"],
            cwd=BASE, capture_output=True, text=True, timeout=30
        )
        out = (checkout_res.stdout + "\n" + checkout_res.stderr).strip()

        # Okamžitě obnovit cache otázek v paměti běžícího serveru
        if "refresh_questions" in globals():
            refresh_questions()

        # Pokud se v banky/ něco změnilo, commitnout a pushnout do vlastního forku (origin)
        status_res = subprocess.run(
            ["git", "status", "--porcelain", "--", "banky"],
            cwd=BASE, capture_output=True, text=True, timeout=15
        )
        if status_res.stdout.strip():
            subprocess.run(["git", "add", "banky"], cwd=BASE, capture_output=True, text=True, timeout=15)
            subprocess.run(
                ["git", "commit", "-m", "chore(banky): auto-sync question banks from upstream/main"],
                cwd=BASE, capture_output=True, text=True, timeout=15
            )
            push_res = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=BASE, capture_output=True, text=True, timeout=30
            )
            out = (out + f"\n[Auto-sync] Nové banky uloženy a pushnuty do origin/main ({push_res.returncode}).").strip()
        else:
            out = "Banky otázek jsou aktuální."

        print(f"[Auto-sync] Výsledek: {out}")
        return out
    except Exception as e:
        print(f"[Auto-sync] Chyba: {e}")
        return str(e)


def sync_worker():
    while True:
        time.sleep(15 * 60)
        git_pull()
