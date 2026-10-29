# Architektura aplikace TZI Trenér

Aplikace pro procvičování teoretické informatiky (KI/TIN) a dalších přednášek.
Postavena na **FastAPI + SQLite** na backendu a modulárním **PWA frontendu s WebAssembly** jádrem.

---

## 1. Celkový přehled a tok dat

```
                   +--------------------------------------------+
                   |  Prohlížeč (PWA klientská část)            |
                   |  ui/novy.html + ui/css/ + ui/js/          |
                   |  (WASM pro matchování doplňovačky v JS)   |
                   +---------------------+----------------------+
                                         | HTTP / REST API (JSON)
                                         v
                   +--------------------------------------------+
                   |  Vstupní bod: server.py                    |
                   |  -> FastAPI aplikace (webapp/main.py)      |
                   +---------------------+----------------------+
                                         |
     +-------------------+---------------+-------------------+
     |                   |                                   |
     v                   v                                   v
+------------+   +-------------------+               +---------------+
| Routers    |   | scoring/          |               | db.py         |
| (webapp/)  |-->| (bodování, streak,|-------------->| (SQLite DB    |
| - auth     |   |  KotH, FFA, duel, |               |  s WAL módem, |
| - study    |   |  lobby místnosti) |               |  transakce)   |
| - account  |   +-------------------+               +---------------+
| - comp     |           |
| - admin    |           v
| - pwa      |   +-------------------+
+------------+   | tzi_trener.py     |
                 | (načítání bank z  |
                 |  banky/*.json)    |
                 +-------------------+
```

---

## 2. Struktura adresářů a souborů

### Backend (`server.py`, `webapp/`, `scoring/`, `db.py`)
- **`server.py`**: Tenký vstupní bod aplikace. Nastavuje port (5051), hostitele a spouští Uvicorn server (`python server.py`). Re-exportuje často používané konstanty pro kompatibilitu s testy.
- **`webapp/`**: Balíček FastAPI aplikace:
  - `config.py`: Načítání proměnných prostředí (`.env`), tajné klíče (`APP_SECRET`, `HASHED_PASSWORD`, `WEBHOOK_SECRET`) a nastavení session cookie.
  - `sessions.py`: Práce se session tokeny (`create_session_token`, `verify_session_token`) a FastAPI závislosti (`require_user`, `require_admin`).
  - `questions.py`: Cache otázek v paměti (`ALL_QUESTIONS`), funkce pro její obnovení (`refresh_questions`) a serverová validace odpovědí proti spoofingu (`verify_answer`).
  - `git_sync.py`: Periodický worker a webhook pro bezkonfliktní synchronizaci složky `banky/` z upstream repozitáře.
  - `pages.py`: Pomocné načítání statických HTML šablon pro přihlášení a administraci.
  - `templates/`: HTML šablony (`login_register.html`, `admin.html`).
  - `routers/`:
    - `auth.py`: Registrace, přihlášení studenta i admina, trial režim a odhlášení.
    - `study.py`: REST API pro načítání přednášek, otázek, progressu a synchronizaci offline fronty.
    - `account.py`: Správa profilu, žebříček, recap, změna hesla/přezdívky a bezpečné mazání dat či profilu.
    - `competitive.py`: API pro King of the Hill (KotH), Free-For-All (FFA), 1v1 duely a kompetitivní místnosti (lobby).
    - `admin.py`: Administrátorský přehled, správa pozvánek.
    - `pwa.py`: Servírování PWA manifestu, Service Workeru (`sw.js`), ikony, WASM binárky a hlavní stránky `/`.
- **`scoring/`**: Modulární systém vyhodnocování a gamifikace:
  - `constants.py`: Globální konstanty bodování (`DAILY_MIN_GOAL`, `KOTH_DEFAULT_QUESTIONS`).
  - `points.py`: Výpočet bodů a obtížnosti, adaptivní streak, evidence pokusů (`record_question_answer`).
  - `daily.py`: Výpočet a reset denního streaku (`get_daily_progress`).
  - `leaderboard.py`: Generování veřejného i admin žebříčku.
  - `koth.py`: Logika vyzývání a obhajoby Krále kopce.
  - `ffa.py`: Hodnocení a leaderboard režimu Free-For-All.
  - `duel.py`: Asynchronní 1v1 duely na shodné sadě otázek.
  - `rooms.py`: Tvorba a správa multiplayerových místností v lobby.
- **`db.py`**: SQLite vrstva, správa tabulek (uživatelé, postupy, statistiky, zápasy), bcrypt hashování hesel, migrace a transakce.
- **`tzi_trener.py`**: Modul načítání JSON bank ze složky `banky/` a legacy stdlib server (sdílený s upstreamem).

---

### Frontend (`ui/`)
Uživatelské rozhraní je postavené bez nutnosti npm buildu (čisté CSS a JS skripty) a běží jako PWA:
- **`ui/novy.html`**: Čistá HTML kostra aplikace (sekce pro Menu, Kvíz, Výsledky, Profil, Žebříček, Arénu a modální okna).
- **`ui/css/style.css`**: Kompletní styly rozhraní, témata (Catppuccin Macchiato, Latte atd.), responzivní layout a KaTeX integrace.
- **`ui/js/`**: Modulárně rozdělený klientský kód:
  - `core.js`: Globální stav kvízu, utility pro zobrazení/skrývání obrazovek, normalizaci a míchání voleb.
  - `format.js`: KaTeX parser pro LaTeX matematické výrazy a převodník notace.
  - `shell.js`: Uživatelský kontext, toast notifikace, přepínání témat a zvuků.
  - `offline.js`: PWA offline fronta v `localStorage`, synchronizace odpovědí po návratu online a prefetch bank.
  - `gamification.js`: Denní streak progress bar, výpočet ranků a odznáčků (achievement mask).
  - `account.js`: Profilové zobrazení, rekapitulace úspěšnosti podle přednášek, modály pro změnu údajů a smazání.
  - `arena.js`: Zobrazení a přepínání soutěžních podstránek Arény (FFA, 1v1, KotH, Místnosti).
  - `rooms.js`: Správa místností v lobby (tvorba místnosti, připojení, polling stavu, spuštění hostitelem).
  - `menu.js`: Načtení seznamu přednášek, filtrování (Teorie / Příklady / Doplňovačka / Vše) a statistiky menu.
  - `chunks.js`: Režim procházení otázek po blocích (např. po 10).
  - `modes.js`: Spouštění studijních režimů (Ostrý test, Náhodný výběr, Jen chybné, Sudden Death).
  - `comp_modes.js`: Klientská logika pro spuštění KotH, FFA a duelů.
  - `recall.js`: Režim Doplňovačka, nahrání WebAssembly jádra (`quiz.wasm`) a fuzzy vyhodnocování překlepů.
  - `quiz.js`: Hlavní kvízová smyčka, renderování otázek (`choice` / `input`), obsluha klávesových zkratek a zobrazení výsledků.
- **`ui/sw.js`**: Service Worker (verze cache `v9`) pro offline caching statických souborů, API endpointů a PWA instalaci.
- **`ui/quiz.wasm`**: Zkompilované AssemblyScript jádro pro rychlé a přesné klientské porovnávání odpovědí.

---

## 3. Banky otázek (`banky/`)
- Jedna přednáška = jeden JSON soubor (`banky/NN-RRRR-MM-DD.json`).
- Otázky pro doplňovačku jsou umístěny v `banky/doplnovacka/`.
- Generovací skripty `build_bank*.py` slouží pro odvození početních příkladů a jejich správných výsledků.
