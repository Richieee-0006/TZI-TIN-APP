# TZI Trenér

Kvíz na opakování přednášek KI/TIN. Vzor: MTCNA-app (stejné režimy a UI).

## Soubory

- `tzi_trener.py`: server (stdlib `http.server`, port 5051), výběr UI (`?ui=`, cookie `tzi_ui`, `--klasicky`) a `/api/*` routy.
- `ui/novy.html`: nové UI (výchozí), inline CSS a JS, barvy a písma přes proměnné v `:root`, dark mód.
- `ui/klasicky.html`: původní UI beze změny (jen odkaz „Nový vzhled“). Zálohy: `zaloha/tzi_trener_v1.py`, git tag `ui-v1-klasicky`.
- `banky/*.json`: jedna banka na přednášku, aplikace je najde sama. Typy otázek: `choice` (options, correct, explanation) a `input` (answer, solution).
- `build_bank.py`, `build_bank_2.py`, `build_bank_3.py`: generují banku 1., 2. a 3. přednášky. Příklady na výsledek se počítají ve skriptu, odpovědi neměnit ručně v JSON.
- `build_bank_dukazy.py`: speciální sada „Důkazy (sada na cvičení)“ (`banky/02d-dukazy.json`, vede se jako 2. přednáška, id `2d-N`): přímý, nepřímý důkaz, sporem a indukce.
- `progress.json`: postup, vzniká za běhu, není v gitu.

## Nová přednáška

Přidat nový soubor `banky/NN-RRRR-MM-DD.json` (id otázek `N-číslo`, aby byly unikátní napříč přednáškami). Pro výpočetní otázky použít funkce z `build_bank.py` a odpovědi ověřit nezávisle.

## Pravidla

- Každý dokument z AI má mít deklaraci využití AI (viz README).
- UI měnit v `ui/novy.html`; `ui/klasicky.html` jen při opravě chyby. Logika (JS) je v obou UI stejná, id elementů nepřejmenovávat.
- Staré screenshoty jsou v `docs/screenshots/legacy/`.
