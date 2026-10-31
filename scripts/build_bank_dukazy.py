#!/usr/bin/env python3
"""Vygeneruje speciální sadu „Důkazy“ (příprava na cvičení) do banky/.

Deklarace využití AI: vytvořeno s pomocí nástroje Claude Sonnet 5.5 (Anthropic, 2026),
uvedeno v souladu se Směrnicí rektora UJEP č. 7/2026 (dobrovolně).

Obsah vychází z příkladů z cvičení (x > 5 ⇒ x > 3 přímo, nepřímo a sporem, součet 1 + 2 + ... + n
indukcí). Ke každé metodě jsou další dva podobné příklady, vždy jedno zadání na příklad (bez ABCD, student počítá sám). Teorii je třeba kontrolovat proti sylabu KI/TIN.
Spuštění:  python3 build_bank_dukazy.py
"""
import json
from pathlib import Path


def ineq(a, b):
    """Tři zadání k (x > a) ⇒ (x > b), a > b: přímý, nepřímý, sporem (jako na cvičení pro a = 5, b = 3).
    Tvar: (zadání, podrobné řešení). Student počítá sám, řešení se odhalí tlačítkem."""
    return [
        (f"Dokaž přímo: (x > {a}) ⇒ (x > {b}).",
         f"Přímý důkaz: předpokládáme, že platí x > {a}, a po krocích dojdeme k x > {b}.\n"
         f"1. Předpoklad: x > {a}.\n"
         f"2. Číselná nerovnost {a} > {b} platí.\n"
         f"3. Nerovnost je tranzitivní: z x > {a} a {a} > {b} plyne x > {b}.\n"
         f"Zápis: (x > {a}) ∧ ({a} > {b}) ⇒ (x > {b}), tedy x > {a} > {b}. Hotovo."),
        (f"Dokaž nepřímo: (x > {a}) ⇒ (x > {b}).",
         f"Nepřímý důkaz: místo x ⇒ y dokážeme obměnu ¬y ⇒ ¬x (platí x ⇒ y ⇔ ¬y ⇒ ¬x).\n"
         f"1. x je x > {a}, y je x > {b}.\n"
         f"2. ¬y je x ≤ {b} a ¬x je x ≤ {a}.\n"
         f"3. Dokazujeme obměnu: (x ≤ {b}) ⇒ (x ≤ {a}).\n"
         f"4. Předpokládáme x ≤ {b}. Protože {b} ≤ {a}, plyne x ≤ {b} ≤ {a}, tedy x ≤ {a}.\n"
         f"Zápis: (x ≤ {b}) ∧ ({b} ≤ {a}) ⇒ (x ≤ {a}). Obměna platí, tedy platí i původní implikace."),
        (f"Dokaž sporem: (x > {a}) ⇒ (x > {b}).",
         f"Důkaz sporem: předpokládáme, že implikace neplatí, tedy platí x ∧ ¬y, a odvodíme spor.\n"
         f"1. Předpoklad sporu: x > {a} ∧ x ≤ {b}.\n"
         f"2. Z x > {a} a {a} > {b} plyne x > {b}.\n"
         f"3. Máme x > {b} ∧ x ≤ {b}, to je spor.\n"
         f"4. Předpoklad sporu neplatí, takže implikace (x > {a}) ⇒ (x > {b}) platí."),
    ]


X0 = [
    ("Dokaž přímo: (x > 0) ⇒ (x + 2 > 2).",
     "Přímý důkaz: předpokládáme x > 0 a dojdeme k x + 2 > 2.\n"
     "1. Předpoklad: x > 0.\n"
     "2. K oběma stranám přičteme 2 (nerovnost se nezmění): x + 2 > 0 + 2.\n"
     "3. Tedy x + 2 > 2. Hotovo.\n"
     "Dosazení jedné hodnoty (třeba x = 1) by nic nedokázalo, x je libovolné."),
    ("Dokaž nepřímo: (x > 0) ⇒ (x + 2 > 2).",
     "Nepřímý důkaz: dokážeme obměnu ¬y ⇒ ¬x.\n"
     "1. x je x > 0, y je x + 2 > 2.\n"
     "2. ¬y je x + 2 ≤ 2 a ¬x je x ≤ 0.\n"
     "3. Dokazujeme obměnu: (x + 2 ≤ 2) ⇒ (x ≤ 0).\n"
     "4. Předpokládáme x + 2 ≤ 2. Odečteme 2 od obou stran: x ≤ 0.\n"
     "Obměna platí, tedy platí i původní implikace."),
    ("Dokaž sporem: (x > 0) ⇒ (x + 2 > 2).",
     "Důkaz sporem: předpokládáme x ∧ ¬y a odvodíme spor.\n"
     "1. Předpoklad sporu: x > 0 ∧ x + 2 ≤ 2.\n"
     "2. Z x + 2 ≤ 2 odečtením 2 plyne x ≤ 0.\n"
     "3. Máme x > 0 ∧ x ≤ 0, to je spor.\n"
     "4. Předpoklad sporu neplatí, takže implikace platí."),
]

INDUKCE = [
    ("Dokaž indukcí: 1 + 2 + ... + n = n(n + 1)/2 pro všechna n ≥ 1.",
     "1. Základní krok (n = 1): levá strana je 1, pravá 1 · 2 / 2 = 1. Platí.\n"
     "2. Indukční předpoklad: pro nějaké k platí 1 + 2 + ... + k = k(k + 1)/2.\n"
     "3. Indukční krok: chceme 1 + 2 + ... + k + (k + 1) = (k + 1)(k + 2)/2.\n"
     "   Levá strana = k(k + 1)/2 + (k + 1)            (použili jsme předpoklad)\n"
     "   = (k + 1) · (k/2 + 1) = (k + 1)(k + 2)/2.     (vytkli jsme k + 1)\n"
     "To je pravá strana pro n = k + 1. Podle principu matematické indukce vzorec platí pro všechna n ≥ 1."),
    ("Dokaž indukcí: 1 + 3 + 5 + ... + (2n − 1) = n² pro všechna n ≥ 1.",
     "1. Základní krok (n = 1): levá strana je 1, pravá 1² = 1. Platí.\n"
     "2. Indukční předpoklad: pro nějaké k platí 1 + 3 + ... + (2k − 1) = k².\n"
     "3. Indukční krok: přidáme další člen 2(k + 1) − 1 = 2k + 1.\n"
     "   Levá strana = k² + (2k + 1)                   (použili jsme předpoklad)\n"
     "   = (k + 1)².                                   (vzorec (a + b)²)\n"
     "To je pravá strana pro n = k + 1. Podle principu matematické indukce vzorec platí pro všechna n ≥ 1."),
    ("Dokaž indukcí: 2 + 4 + 6 + ... + 2n = n(n + 1) pro všechna n ≥ 1.",
     "1. Základní krok (n = 1): levá strana je 2, pravá 1 · 2 = 2. Platí.\n"
     "2. Indukční předpoklad: pro nějaké k platí 2 + 4 + ... + 2k = k(k + 1).\n"
     "3. Indukční krok: přidáme další člen 2(k + 1).\n"
     "   Levá strana = k(k + 1) + 2(k + 1)             (použili jsme předpoklad)\n"
     "   = (k + 1)(k + 2).                             (vytkli jsme k + 1)\n"
     "To je pravá strana pro n = k + 1. Podle principu matematické indukce vzorec platí pro všechna n ≥ 1."),
]

# pořadí: přímý ×3, nepřímý ×3, sporem ×3, indukce ×3
_I = [ineq(5, 3), ineq(8, 2), X0]
TASKS = [ex[m] for m in range(3) for ex in _I] + INDUKCE


def self_check():
    imp = lambda p, q: int((not p) or q)
    vals = [v / 4 for v in range(-120, 120)]
    for a, b in ((5, 3), (8, 2)):
        assert a > b
        assert all(imp(x > a, x > b) == imp(x <= b, x <= a) == 1 for x in vals)
        # předpoklad sporu x > a ∧ x ≤ b nemá řešení
        assert not any(x > a and x <= b for x in vals)
    assert all(imp(x > 0, x + 2 > 2) == imp(x + 2 <= 2, x <= 0) == 1 for x in vals)
    assert not any(x > 0 and x + 2 <= 2 for x in vals)
    # indukce: vzorce a kroky
    for n in range(1, 300):
        assert sum(range(1, n + 1)) == n * (n + 1) // 2
        assert sum(2 * i - 1 for i in range(1, n + 1)) == n * n
        assert sum(2 * i for i in range(1, n + 1)) == n * (n + 1)
        assert n * (n + 1) // 2 + (n + 1) == (n + 1) * (n + 2) // 2
        assert n * n + (2 * n + 1) == (n + 1) ** 2
        assert n * (n + 1) + 2 * (n + 1) == (n + 1) * (n + 2)


def main():
    self_check()
    # reveal: bez políčka na odpověď, řešení se odhalí tlačítkem (UI: isReveal)
    qs = [{"type": "input", "reveal": True, "text": t, "solution": sol} for t, sol in TASKS]
    for i, q in enumerate(qs, 1):
        q["number"] = i
        q["id"] = f"2d-{i}"
    out = {"title": "Důkazy (sada na cvičení)", "lecture": 2, "date": "2026-10-08", "questions": qs}
    path = Path(__file__).parent / "banky" / "02d-dukazy.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path.name}: {len(qs)} zadání (bez výběru ABCD)")


if __name__ == "__main__":
    main()
