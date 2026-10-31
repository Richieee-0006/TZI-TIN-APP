# TZI Trenér - Vývoj

Kvíz na opakování KI/TIN.

## Struktura
Více v [ARCHITECTURE.md](ARCHITECTURE.md).

- **Backend:** `server.py` (entry), `webapp/` (API/auth), `scoring/` (body), `db.py` (SQLite).
- **Frontend:** `ui/novy.html`, `ui/css/`, `ui/js/` (PWA).
- **Data:** `banky/*.json`. Generují se skripty.
- **Nástroje:** `scripts/build_*.py` (generátory), `tests/test_*.py` (pytest).

## Nová přednáška
Vytvoř nový soubor v `banky/NN-RRRR-MM-DD.json`.
Pro výpočty přidej skript v `scripts/` (ověř odpovědi nezávisle).
ID otázky formát: `N-číslo`.

## Pravidla
- **Deklarace AI:** Každý AI výstup musí mít zmínku v README.
- **Možnosti:** `choice` otázky se v UI míchají. Nikdy nepoužívej "A i B", "první možnost" atd. v textech.
- **UI:** Upravuj `ui/novy.html` a js/css moduly. `klasicky.html` je legacy (nevyvíjí se).
