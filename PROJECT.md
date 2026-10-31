# Project: TZI-TIN-APP Security Fixes (Pentest Hardening)

## Architecture
- Root Directory: `/home/richieee/TZI-TIN-APP`
- Frontend: `ui/` static PWA (`ui/novy.html`, `ui/js/`, `ui/css/`) and templates (`webapp/templates/`)
- Backend WebApp: `webapp/` FastAPI application (`server.py`, `webapp/routers/`, `webapp/questions.py`, `webapp/sessions.py`)
- Scoring & Game Engine: `scoring/` (`scoring/koth.py`, `scoring/rooms.py`, `scoring/ffa.py`, `scoring/duel.py`, `scoring/points.py`)
- Database: SQLite WAL (`db.py`, `tzi.db`)

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | R1: UI Option Toggling | Radio-button switch behavior for single-choice questions in `ui/js/quiz.js` | M1 | TODO.md & Pentest |
| 2 | R9: Remove Invite Card | Remove obsolete invitation generator card from `webapp/templates/admin.html` | M1 | TODO.md & Pentest |
| 3 | R2: Anti-spoofing in /api/progress | Require userKeys/user_answer, eliminate isCorrect fallback, server-verify in `webapp/routers/study.py` | M2 | TODO.md & Pentest |
| 4 | R7: Log DB Flood Protection | IP sliding-window rate limiting on `/api/client-error` returning HTTP 429 without DB writes | M2 | TODO.md & Pentest |
| 5 | R8: Webhook Timing Attack Fix | Use `secrets.compare_digest` in `webapp/routers/pwa.py` for WEBHOOK_SECRET | M2 | TODO.md & Pentest |
| 6 | R3: KotH Exploit Fix | Require `answers` array in `/api/koth/submit`, eliminate `correct_count` branch and client isCorrect | M3 | TODO.md & Pentest |
| 7 | R4: Multiplayer Score Anti-Spoofing | Remove `explicit_score` parameter from `scoring/rooms.py` and `webapp/routers/competitive.py` | M3 | TODO.md & Pentest |
| 8 | R5: Self-Duel Farming Prevention | Return HTTP 400 when `opponent_id == uid` in `/api/duel/start` | M3 | TODO.md & Pentest |
| 9 | R6: FFA Time Manipulation Fix | Require server-side `answers` validation and enforce `time_ms >= 5000` in `/api/ffa/submit` | M3 | TODO.md & Pentest |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Frontend & Admin UI Security | `ui/js/quiz.js`, `webapp/templates/admin.html` | none | DONE |
| M2 | Study & System API Hardening | `webapp/routers/study.py`, `webapp/questions.py`, `webapp/routers/pwa.py` | none | DONE |
| M3 | Competitive & Scoring Hardening | `scoring/rooms.py`, `webapp/routers/competitive.py`, `scoring/koth.py`, `scoring/ffa.py`, `scoring/duel.py` | none | DONE |
| M4 | Final E2E Verification & Regressions | Full test suite (`tests/`), regression prevention, audit clean | M1, M2, M3 | DONE |

## Interface Contracts
### Client ↔ Study Router (`/api/progress`)
- Payload MUST include `"latest"` with valid `"id"` and either `"userKeys"` (list) or `"user_answer"` (str)
- Server validates answer against question bank; returns HTTP 400 if question or answer is missing

### Client ↔ Competitive Router (`/api/koth/submit`, `/api/ffa/submit`)
- Payload MUST include `"answers"`: list of `{"id": str, "userKeys": list | "user_answer": str}`
- `"correct_count"` and `"score"` fields are rejected / ignored; score computed strictly server-side
- `/api/ffa/submit`: `time_ms < 5000` raises HTTP 400

### Client ↔ Duel Router (`/api/duel/start`)
- If payload provides `opponent_id` and `opponent_id == current_user.id`, raises HTTP 400

### Room Scoring Contract (`scoring/rooms.py`)
- Function `submit_comp_room_result` signature: `(room_code: str, user_id: int, user_name: str, correct_count: int, time_ms: int)` -> dict
- `explicit_score` parameter removed completely

## Code Layout
- `/home/richieee/TZI-TIN-APP/`
  - `ui/js/quiz.js` (M1)
  - `webapp/templates/admin.html` (M1)
  - `webapp/routers/study.py`, `webapp/routers/pwa.py`, `webapp/questions.py` (M2)
  - `scoring/rooms.py`, `scoring/koth.py`, `scoring/ffa.py`, `scoring/duel.py`, `webapp/routers/competitive.py` (M3)
  - `tests/test_features.py`, `tests/test_server_api.py`, `tests/test_system.py`, `tests/test_doplnovacka.js` (M1, M2, M3, M4)
