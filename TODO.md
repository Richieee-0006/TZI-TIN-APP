# TZI Trenér: plán do budoucna

Z ponytail auditu a review (22. 10. 2026). Dělat, až bude chuť. Pořadí podle důležitosti. Klasický vzhled se neřeší, má jen upozornění, že se už nevyvíjí.

Deklarace využití AI: seznam sestavil Claude Sonnet 5.5 (Anthropic, 2026) z auditu kódu, nálezy jsou ověřené čtením kódu.

## Opravit dřív

1. **Zápis postupu přes dočasný soubor** (`tzi_trener.py`, `save_progress`/`load_progress`). Proces zabitý uprostřed zápisu nechá poškozený `progress.json`, čtení chybu spolkne a další zápis přepíše vše prázdným. Oprava: zapsat do `progress.json.tmp` a `os.replace(tmp, PROGRESS_FILE)`. Přidat malý test s poškozeným souborem.
2. **Zadání na rozbor (`reveal`) v Ostrém testu a Sudden Death** (`ui/novy.html`, `examNext`, `confirmAnswer`, výběr otázek). V Ostrém testu „Ukázat řešení" otázku jen přeskočí a nepočítá se. V Sudden Death „Nezvládl jsem" hru neukončí. Oprava: do výběru pro oba režimy přidat `.filter(q => !q.reveal)`. Pak projít oba režimy na sadě Důkazy a „Všechny přednášky".

## Až bude čas

3. **Dvě karty prohlížeče si přepíšou postup** (`tzi_trener.py`, POST `/api/progress`, `d["seen"] = payload["seen"]`). Při počítači a telefonu naráz vyhraje poslední odeslání. Oprava: sloučit s uloženou mapou (asi 5 řádků).
4. **Test sebehodnocení** (`gradeTask`, Zvládl/Nezvládl, Uznat jako správně). `test_doplnovacka.js` pokrývá jen porovnávání odpovědí. Doplnit scénář nebo malý test s `vm`.
5. **README je zastaralé.** Chybí zadání na rozbor, Doplňovačka, banky 3, 4 a kombinatoriky. Buď doplnit, nebo odkázat na `CLAUDE.md`.
6. **Výchozí zdroj je Kombinatorika** (`list_sources`, `default = real[-1]`). Vybrat výchozí banku výslovně (hlavní banka 4. přednášky).
7. **`/api/sources` bez ošetření chyb.** Rozbitý JSON nebo chybějící `date` v jedné bance shodí menu. Obalit jako `/api/questions`.
8. **Špatné tělo POST** (`Content-Length`, JSON jako seznam). Ošetřit `ValueError` a `AttributeError` odpovědí 400.
9. **`.gitignore`:** přidat `graphify-out/` a `.claude/`.
10. **Commit a push** všeho neuloženého (banky 4 a kombinatoriky, doplňovačka, `build_bank_recall.py`, `test_doplnovacka.js`, TODO, upravené UI). Až po míchání možností a po opravě bodu 2.

## Nápady

- Po další přednášce doplnit variace a kombinace s opakováním (banka 4k, doplňovačka).
- Zvážit smazání klasického vzhledu a `zaloha/` (původní stav je v git tagu `ui-v1-klasicky`, bylo by to asi -780 řádků).
