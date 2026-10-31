# TZI-TIN-APP — Security & Architektura

## 1. Auth & Session
- **Cookie:** `tzi_session` (signed JWT přes `itsdangerous`). 30 dní, httponly, samesite=lax, secure.
- **Login:** `/login` ověří `bcrypt`, vydá cookie.
- **Trial:** `/trial` dává user_id=0, role=trial. Žádný zápis do DB.
- **Routy:** `/api/*` vyžaduje token. `/admin` vyžaduje role=admin.

## 2. Anti-spoofing
- Server validuje všechny vstupy (`webapp/questions.py:verify_answer`).
- `choice`: `set(correct) == set(user_keys)`.
- `input`: `norm_str()` (bez mezer a diakritiky).
- `recall`: Kanonický tvar + Lev1 distance (WASM/Python).

## 3. Bodování (`scoring/`)
- 1. pokus: 3x. 2. pokus: 1x. Recall: 5x.
- Těžké otázky (<30% správnost): 2.0x.
- Streak > 5: +2 body.
- KOTH: Skóre = `correct * 100 + rychlost`.

## 4. DB (SQLite)
- WAL mód. Transakce přes `with conn`.
- Tabulky: `users`, `user_scores`, `user_answers`, `question_stats`, `daily_progress`, KOTH/FFA stavy.

## 5. API
- **Auth:** `/login`, `/register`, `/trial`, `/logout`.
- **Study:** `/api/sources`, `/api/questions`, `/api/progress`, `/api/sync`.
- **Hry:** `/api/koth/*`, `/api/ffa/*`, `/api/duel/*`, `/api/rooms/*`.
- **Účet:** `/api/leaderboard`, `/api/account/*`.

## 6. Security Hlavičky
- `X-Frame-Options: DENY`, `CSP: default-src 'self'`, `Referrer-Policy: strict-origin`.
- Rizika: Chybí CSRF u formulářů, Secure=True blokuje HTTP localhost, bez rate-limitu na auth.

## 7. Offline PWA
- `ui/sw.js` cache. Odpovědi do `localStorage`.
- Dávkový `POST /api/sync` (max 100), server přepočítá a spojí.
