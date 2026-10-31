# Architektura TZI Trenér

App pro KI/TIN. FastAPI + SQLite + PWA WebAssembly.

## 1. Data flow

```
[Prohlížeč PWA ui/novy.html + WASM]
       | HTTP/REST JSON
       v
[server.py -> webapp/main.py (FastAPI)]
       |
+------+------+------+
v             v      v
webapp/routers/ scoring/ db.py(SQLite)
```

## 2. Složky

**`webapp/` (FastAPI backend):**
- `config.py`: env vars, secrets.
- `sessions.py`: auth, session cookie.
- `questions.py`: cache, server validace.
- `git_sync.py`: webhook sync bank.
- `routers/`: auth, study, account, competitive, admin, pwa.

**`scoring/` (Body a hry):**
- `points.py`: body, streak.
- `daily.py`: denní cíle.
- `leaderboard.py`: žebříček.
- `koth.py`, `ffa.py`, `duel.py`, `rooms.py`: hry.

**Kořen:**
- `server.py`: start, uvicorn na 5051.
- `db.py`: SQLite WAL, auth, transakce.
- `tzi_trener.py`: načítání JSON bank.

**Nové složky:**
- `scripts/`: `build_*.py` pro banky a WASM.
- `tests/`: pytest `test_*.py` a `test_*.js`.
- `banky/`: `*.json` s otázkami, `doplnovacka/`.

**`ui/` (Frontend PWA):**
- `novy.html`: SPA kostra.
- `css/style.css`: styly, Catppuccin.
- `js/`: `core`, `quiz`, `offline` (sync), `arena`.
- `sw.js`: Service worker.
- `quiz.wasm`: rychlé porovnávání.
