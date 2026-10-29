# TZI Trenér: plán do budoucna

Z ponytail auditu a review (22. 10. 2026). Dělat, až bude chuť. Pořadí podle důležitosti. Klasický vzhled se neřeší, má jen upozornění, že se už nevyvíjí.

Deklarace využití AI: seznam sestavil Claude Sonnet 5.5 (Anthropic, 2026) z auditu kódu, nálezy jsou ověřené čtením kódu.

## Hotovo

- [x] **Přechod na FastAPI + SQLite:** Multi-user systém s unikátními anonymními přezdívkami podle témat (GDPR/ÚOOÚ), streak bodování s adaptivní obtížností a anonymní žebříček.
- [x] **Catppuccin téma a Daily Cat (:3):** Pastelový vzhled s denní kočičkou.
- [x] **Trial mód:** Možnost vyzkoušet aplikaci bez nutnosti registrace a ukládání progressu.
- [x] **Admin autentizace:** Opraven hash bcrypt hesla v `.env`, odstraněn nápis Admin z veřejného přihlašovacího formuláře (přihlášení adminem funguje zadáním uživatele admin).
- [x] **Oprava JS syntaxe v `novy.html`:** Opraveny interpolace uživatelských dat při načtení profilu.
- [x] **Zadání na rozbor (`reveal`) v Ostrém testu a Sudden Death:** Přidán `.filter(q => !q.reveal)`.
- [x] **Zápis postupu přes databázi:** Původní `progress.json` nahrazen SQLite databází s transakcemi v WAL režimu.
- [x] **`.gitignore`:** Přidáno `.env`, `tzi.db*`, `.venv/`, `graphify-out/`, `.claude/`.

## Až bude čas

1. Test sebehodnocení (`gradeTask`, Zvládl/Nezvládl, Uznat jako správně).
2. README aktualizace (popsat FastAPI, SQLite, multi-user, témata, trial mód).
3. Commit a push změn do repozitáře.

## Nápady

- Po další přednášce doplnit variace a kombinace s opakováním (banka 4k, doplňovačka).
- Zvážit smazání klasického vzhledu a `zaloha/` (původní stav je v git tagu `ui-v1-klasicky`, bylo by to asi -780 řádků).
