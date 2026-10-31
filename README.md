# TZI Trenér

App pro KI/TIN. Web, FastAPI, SQLite, PWA, WebAssembly.
Spouští se bez závislostí. Čte `ui/*.html` a `banky/*.json`.

## Start
```bash
python3 server.py          # http://127.0.0.1:5051
python3 server.py --lan    # i na síti
```

## Funkce
- **Přednášky:** Banky z `banky/*.json`. Tři typy (Teorie, Příklady, Doplňovačka).
- **Režimy:** Po X, Vše, Jen chyby, Ostrý test, Sudden Death, Studuj.
- **Ukládání:** Lokální POST přes `/api/progress`, SQLite WAL v `db.py`.
- **UI:** Dvě verze. Nový (PWA, WASM), Starý (legacy, HTML/JS).

## Architektura
Viz [ARCHITECTURE.md](ARCHITECTURE.md).

## Vývoj (banky)
Přednáška = `banky/NN-RRRR-MM-DD.json`.
Generování přes `scripts/build_*.py` pro jistotu správných výsledků.

## Licence
MIT. Obsah (AI + poznámky autora).
