# TZI Trenér: TODO

Pořadí podle priority.

## Bezpečnostní opravy (z pentestu)
- [x] **Fix přepínání možností (UI bug)**: V `ui/js/quiz.js:149` řádek `if (selected.size >= q.correct.length) return;` brání vybrat jinou možnost, když už je jedna vybraná! U jednovolbových otázek (`q.correct.length === 1`) musí kliknutí na novou možnost automaticky odznačit předchozí (chování radio buttonu).
- [x] **Fix Anti-spoofing v `/api/progress`**: Zakázat fallback na `latest_answer.get("isCorrect")`, striktně vyžadovat `userKeys` / `user_answer` a validovat proti bankám otázek.
- [x] **Fix KotH exploit v `/api/koth/submit`**: Odstranit větev `elif "correct_count" in payload:`, vyžadovat pole `answers` a skutečné ověření odpovědí.
- [x] **Fix Multiplayer Score Spoofing**: Odstranit parametr `explicit_score` z `scoring/rooms.py` i `webapp/routers/competitive.py`. Skóre musí počítat pouze server.
- [x] **Fix Self-Duel Farming v `/api/duel/start`**: Přidat kontrolu `if opponent_id == uid: raise HTTPException(400, "Nelze vyzvat sám sebe.")`.
- [x] **Fix FFA Time Manipulation v `/api/ffa/submit`**: Odstranit `correct_count` parametr, validovat pole `answers` a ošetřit minimální reálný čas (`time_ms < 5000` = podezřelé/nemožné).
- [x] **Fix Log DB Flooding v `/api/client-error`**: Endpoint nemá žádný rate limiting. Kdokoliv může zasypat SQLite databázi miliony falešných error logů.
- [x] **Fix Timing Attack u WEBHOOK_SECRET**: V `webapp/routers/pwa.py:40` se používá `secret != WEBHOOK_SECRET` místo `secrets.compare_digest(secret, WEBHOOK_SECRET)`.
- [x] **Odstranit generátor pozvánek**: Smazat kartu z `webapp/templates/admin.html`.

## Hotovo
- [x] Přechod FastAPI + SQLite (multi-user, streak, leaderboard).
- [x] Catppuccin téma.
- [x] Trial mód (bez ukládání).
- [x] Admin login (bez nápisu v UI).
- [x] Oprava JS syntaxe (profil).
- [x] Skrytí `reveal` v testech.
- [x] `.gitignore` setup.

## Backlog
- [ ] Test sebehodnocení (Uznat jako správně).
- [ ] README aktualizace (již hotovo zčásti).
- [ ] Doplnit variace a kombinace (banka 4k, doplňovačka).
- [ ] Smazat klasický vzhled (je v git tagu `ui-v1-klasicky`).
