# TZI-TIN-APP — Bezpečnostní & architektonické poznatky

## 1. Autentizace & session

| Parametr | Hodnota |
|---|---|
| Cookie name | `tzi_session` |
| Mechanismus | `itsdangerous.URLSafeTimedSerializer` (signed JWT-ekvivalent) |
| Payload | `{user_id, username, role, theme, ts}` |
| Maximální věk | 30 dní (86400 × 30) |
| Cookie flags | `httponly=True`, `samesite="lax"`, `secure=True` |
| Secure=True | **Na HTTP localhost cookie nepůjde** — prohlížeč ji odmítne |
| Binding | Žádný IP/User-Agent binding — token stačí forwardovat |

**Auth flow:**
1. `POST /register` → `{"username","password","password_confirm"}` → `bcrypt` hash → `Set-Cookie`
2. `POST /login` → ověření `bcrypt` → `Set-Cookie`
3. Všechny `/api/*` routy: `Depends(require_user)` → dekódování cookie → 401/403
4. Admin: `Depends(require_admin)` → role == "admin"

**Trial mód:**
- `GET /trial` → vytvoří fiktivního uživatele `id=0, role=trial`
- Session 24h, data se neukládají do DB
- Blokován: změna jména/hesla, smazání profilu

## 2. Autorizace

| Endpoint | Role | Poznámka |
|---|---|---|
| `/admin` | admin | HTML stránka |
| `/api/*` | student, trial, admin | trial má omezená data |
| `/trial` | veřejný | anonymní přístup |
| `/register` | veřejný | — |
| `/login` | veřejný | — |

## 3. Šifrování & hashe

| Datový typ | Metoda | Poznámka |
|---|---|---|
| Hesla | `bcrypt` | Správně, adaptive cost |
| Session tokeny | `URLSafeTimedSerializer` (HMAC-SHA1 + AES) | Signatura chrání proti manipulaci |
| APP_SECRET | env var, povinný | `RuntimeError` při absenci |
| WEBHOOK_SECRET | env var, volitelný | git webhook autentizace |

## 4. Validace odpovědí (anti-spoofing)

**Klientská role:** pouze posílá `user_answer` (string/list) → server validuje.

**Server-side verify (`webapp/questions.py:verify_answer`):**

| Typ otázky | Algoritmus |
|---|---|
| `choice` | Set equality: `set(correct) == set(user_keys)` |
| `input` | `norm_str()` porovnání + mezery |
| `recall` | Kanonické odpovědi + lev1 edit distance tolerance |

**`norm_str()` pipeline:**
1. `strip_accents()` — odstranění diakritiky
2. `lowercase`
3. `remove non-alnum`
4. `split/join` — normalizace mezer

**Recall tolerance:**
- Case/diacritica/interpunkce insensitive
- 1 překlep u slov >5 písmen (Levenshtein distance 1)
- Více variant: `accept` array

## 5. Bodovací systém

**Body za odpověď (`scoring/points.py:record_question_answer`):**

| Situace | Body |
|---|---|
| První správná (ne-recall) | 3 × multiplier |
| Druhá správná | 1 × multiplier |
| Třetí+ správná | 0 |
| Recall správně | 5 × multiplier |
| Špatně | 0 |

**Multiplier (adaptive difficulty):**
- Správnost <30% → 2.0× (extra těžká)
- Správnost <50% → 1.5× (těžká)
- Správnost ≥50% → 1.0× (standardní)

**Streak bonus:**
- 5+ správných v řadě → +2 body
- Špatná odpověď → reset streaku

**Denní cíl:**
- `DAILY_MIN_GOAL` — počet otázek pro "goal met"
- Denní streak při splnění po sobě jdoucích dnů
- Reset při přerušení kalendářního dne

**KOTH skórování:**
- `score = correct × 100 + speed_bonus`
- Speed bonus: `max(0, 120 - time_seconds)` při `correct > 0`
- Trůn: `challenger_score > king_score`

## 6. Databáze (SQLite)

| Nastavení | Hodnota |
|---|---|
| Journal mode | WAL (Write-Ahead Logging) |
| Připojení | Thread-local |
| Transakce | `with conn:` kontext |

**Tabulky:**

| Tabulka | Klíčová pole |
|---|---|
| `users` | id, username, password_hash, role, theme, created_at |
| `user_scores` | user_id, total_points, current_streak, best_streak, daily_streak, last_goal_date |
| `user_progress` | user_id, source, seen_json, session_json |
| `user_answers` | user_id, question_id, is_correct, attempt_number, points_awarded |
| `question_stats` | question_id, total_attempts, correct_attempts, first_try_correct |
| `daily_progress` | user_id, activity_date, questions_answered, questions_correct, goal_met |
| `koth_state` | king_user_id, king_username, king_score, crowned_at |
| `koth_matches` | challenger/defender info, scores, won_throne |
| `ffa_state`, `ffa_matches` | — |
| `duel_state`, `duel_matches` | — |
| `comp_rooms` | id, name, host_id, status, created_at |

**Hard delete:** `DELETE FROM user_answers WHERE user_id=?` → trvalé smazání

## 7. API Endpoints

### Auth
| Method | Path | Auth | Popis |
|---|---|---|---|
| GET | `/login` | — | Login page |
| POST | `/login` | — | `username` + `password` → redirect |
| GET | `/register` | — | Register page |
| POST | `/register` | — | `username` + `password` + `password_confirm` → redirect |
| GET | `/trial` | — | Anonymous session |
| GET | `/logout` | auth | Odhlášení |

### Study
| Method | Path | Auth | Popis |
|---|---|---|---|
| GET | `/api/me` | auth | User profile + stats |
| GET | `/api/daily-progress` | auth | Denní statistiky |
| GET | `/api/sources` | auth | Seznam přednášek |
| GET | `/api/questions?source=N` | auth | Otázky z banky |
| GET | `/api/recall` | auth | Doplňovačky |
| GET | `/api/progress?source=N` | auth | Seen + session stav |
| POST | `/api/progress` | auth | Uložení odpovědi |
| POST | `/api/sync` | auth | Offline sync (max 100 odpovědí) |

### Competitive
| Method | Path | Auth | Popis |
|---|---|---|---|
| GET | `/api/koth/status` | auth | KOTH stav |
| POST | `/api/koth/start` | auth | Začít KOTH |
| POST | `/api/koth/submit` | auth | Odeslat odpověď |
| GET | `/api/ffa/status` | auth | FFA stav |
| POST | `/api/ffa/start` | auth | Začít FFA |
| POST | `/api/ffa/submit` | auth | Odeslat odpověď |
| GET | `/api/duel/status` | auth | Duel stav |
| POST | `/api/duel/start` | auth | Začít duel |
| POST | `/api/duel/submit` | auth | Odeslat odpověď |
| GET | `/api/rooms` | auth | Seznam room |
| POST | `/api/rooms/create` | auth | Vytvořit room |
| GET | `/api/rooms/{id}` | auth | Detail room |
| POST | `/api/rooms/{id}/join` | auth | Připojit se |
| POST | `/api/rooms/{id}/start` | auth | Spustit room |
| POST | `/api/rooms/{id}/leave` | auth | Opustit room |
| POST | `/api/rooms/{id}/submit` | auth | Odeslat odpověď |

### Account
| Method | Path | Auth | Popis |
|---|---|---|---|
| GET | `/api/leaderboard` | auth | Žebříček top 30 |
| GET | `/api/account/recap` | auth | Rekapitulace postupu |
| POST | `/api/account/username` | auth | Změna jména |
| POST | `/api/account/password` | auth | Změna hesla |
| POST | `/api/account/revalidate-delete` | auth | Potvrzení smazání dat |
| POST | `/api/account/delete-profile` | auth | Smazání účtu (3-step) |

### Admin
| Method | Path | Auth | Popis |
|---|---|---|---|
| GET | `/admin` | admin | Přehled uživatelů |

### PWA / Static
| Method | Path | Auth | Popis |
|---|---|---|---|
| GET | `/` | auth | Hlavní stránka → redirect /login |
| GET | `/quiz.wasm` | — | WASM modul |
| GET | `/manifest.webmanifest` | — | PWA manifest |
| GET | `/sw.js` | — | Service worker |
| POST | `/webhook?secret=` | secret | Git auto-sync |

## 8. Security Headers

| Header | Hodnota |
|---|---|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `X-XSS-Protection` | `1; mode=block` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; img-src 'self' data:; font-src 'self' cdnjs.cloudflare.com; worker-src 'self' blob:; connect-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |
| `Cache-Control` | `no-store, no-cache, must-revalidate` |

## 9. Architecture

```
server.py (entry point)
    └── webapp/main.py (FastAPI app)
            ├── webapp/config.py       # env vars, secrets
            ├── webapp/sessions.py     # token management
            ├── webapp/questions.py    # answer verification
            ├── webapp/git_sync.py     # auto-sync
            ├── webapp/pages.py        # HTML templates
            ├── webapp/routers/
            │   ├── auth.py            # login/register/trial
            │   ├── admin.py           # admin panel
            │   ├── study.py           # quiz/progress
            │   ├── account.py         # user settings
            │   ├── competitive.py     # KOTH/FFA/duel/rooms
            │   └── pwa.py             # WASM/manifest/webhook
            ├── scoring/
            │   ├── __init__.py        # re-exports
            │   ├── points.py          # answer scoring
            │   ├── daily.py           # daily goals
            │   ├── leaderboard.py     # ranking
            │   ├── koth.py            # king of hill
            │   ├── ffa.py             # free-for-all
            │   ├── duel.py            # 1v1 duel
            │   └── rooms.py           # lobby rooms
            └── db.py                  # SQLite layer
tzi_trener.py  # question bank loader
banky/*.json   # question banks
ui/            # frontend (HTML/CSS/JS)
```

**Entry point:** `.venv/bin/python server.py`
**Port:** 5051, **Host:** 127.0.0.1
**Server:** uvicorn

## 10. Bezpečnostní rizika

### Kritická

| # | Riziko | Detail |
|---|---|---|
| 1 | **Chybějící CSRF token** | Formuláře nemají CSRF token — POST požadky z externích domén jsou možné |
| 2 | **Secure=True na localhost** | Cookie nepůjde na HTTP → login/login selže na `127.0.0.1:5051` |
| 3 | **Žádný rate limiting** | Brute force login/register možný bez omezení |
| 4 | **WEBHOOK_SECRET volitelný** | Pokud není nastaven, webhook běží bez autentizace |

### Střední

| # | Riziko | Detail |
|---|---|---|
| 5 | **Session token bez bindingu** | Token lze forwardovat — session hijacking |
| 6 | **Heslo v plaintext v request body** | POST /register a /login posílí heslo v plaintext (nutnost HTTPS) |
| 7 | **HSMF na delete** | Smazání profilu vyžaduje password, ale není rate limit na selhání |
| 8 | **Recall tolerance — lev1** | Tolerance 1 překlepu může umožnit špatné odpovědi |
| 9 | **XSS přes uživatelské vstup** | Uživatelské vstupy (username) se escapují při renderování, ale POST data se nevalidují striktně |

### Nízká

| # | Riziko | Detail |
|---|---|---|
| 10 | **CSP whitelist cdn.jsdelivr.net** | Externí CDN — teoretický XSS přes compromise CDN |
| 11 | **SQLite WAL** | Soubor databáze je přístupný přímo — obcházení validace |
| 12 | **Náhodnost ID room** | Room ID generováno bez CSRF tokenu |

## 11. Deployment konfigurace

| Proměnná | Povinná | Výchozí | Popis |
|---|---|---|---|
| `APP_SECRET` | **Ano** | — | Signing key pro session tokeny |
| `HASHED_PASSWORD` | Ne | — | bcrypt hash pro admin login |
| `WEBHOOK_SECRET` | Ne | — | Autentizace git webhooku |

**.env soubor:** Načítán přes `python-dotenv` z pracovního adresáře.

## 12. Frontend architektura

**Soubor:** `ui/novy.html` (PWA)

**JS moduly (14):**
| Modul | Účel |
|---|---|
| `shell.js` | Základní layout & routing |
| `menu.js` | Hlavní menu & navigace |
| `core.js` | Základní UI komponenty |
| `format.js` | KaTeX rendering |
| `quiz.js` | Quiz režim (choice/input) |
| `recall.js` | Doplňovačka režim |
| `modes.js` | Teorie/Příklady režimy |
| `chunks.js` | Otázka po otázce |
| `comp_modes.js` | KOTH/FFA/duel |
| `rooms.js` | Lobby room |
| `offline.js` | Sync & cache |
| `gamification.js` | Streak/body/žebříček |
| `arena.js` | Arena UI |
| `account.js` | Nastavení účtu |

**Data flow:**
1. `GET /api/sources` → seznam přednášek
2. `GET /api/questions?source=N` → otázky
3. Uživatel odpoví → `POST /api/progress` → body/streak
4. Offline: odpovědi do localStorage → `POST /api/sync` při reconnect

**Styling:** Catppuccin téma, CSS proměnné, dark/light mód.

## 13. Recall systém

**Složka:** `banky/doplnovacka/`
**Endpoint:** `GET /api/recall`
**ID otázek:** začíná `r-`

**Formát JSON:**
```json
{
  "questions": [
    {
      "id": "r-N",
      "category": "název_kategorie",
      "accept": ["kanonická_odpověď", "varianta2"],
      "words": "1-2",
      "explanation": "vysvětlení"
    }
  ]
}
```

**Validace:** `norm_str(user_answer) == norm_str(variant)` nebo Levenshtein distance ≤1 pro slova >5 písmen.

## 14. Competitive režimy — detaily

### King of the Hill
- Jeden držitel trůnu (`koth_state`)
- Výzva: `correct × 100 + speed_bonus`
- Nový král: `challenger_score > king_score`
- Obrany se počítají při úspěšné obraně

### Free-for-All
- Každý sám proti sobě
- Status + submit flow jako KOTH

### Duel
- 1v1 souboj s request/response pattern
- `duel_state` ukládá výzvu i odpověď

### Rooms (Lobby)
- Vlastní místnosti s hostitelem
- `comp_rooms` tabulka
- Statusy: `waiting`, `active`, `finished`

## 15. Off-line režim

**Mechanismus:**
1. Service Worker (`ui/sw.js`) cacheuje statické assety
2. Odpovědi se ukládají do `localStorage`
3. `POST /api/sync` — dávková synchronizace (max 100 odpovědí)
4. Server ověří duplikáty a přepočítá body

**Data v localStorage:**
- `tzi_answers_pending` — čekající odpovědi
- `tzi_progress` — lokální stav postupu
