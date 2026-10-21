#!/usr/bin/env python3
"""Vygeneruje speciální sadu „Důkazy“ (příprava na cvičení) do banky/.

Deklarace využití AI: vytvořeno s pomocí nástroje Claude Sonnet 5.5 (Anthropic, 2026),
uvedeno v souladu se Směrnicí rektora UJEP č. 7/2026 (dobrovolně).

Obsah vychází z příkladů z cvičení (x > 5 ⇒ x > 3 přímo, nepřímo a sporem, součet 1 + 2 + ... + n
indukcí). Ke každé metodě jsou další dva podobné příklady, vždy jedna otázka na příklad. Teorii je třeba kontrolovat proti sylabu KI/TIN.
Spuštění:  python3 build_bank_dukazy.py
"""
import json
import random
from pathlib import Path


def ineq(a, b):
    """Tři otázky k (x > a) ⇒ (x > b), a > b: přímý, nepřímý, sporem (jako na cvičení pro a = 5, b = 3)."""
    return [
        (f"Přímý důkaz (x > {a}) ⇒ (x > {b}): který zápis je správný?",
         [f"x > {a} ∧ {a} > {b} ⇒ x > {b}", f"x > {b} ∧ {b} > {a} ⇒ x > {a}",
          f"x ≤ {b} ∧ {b} ≤ {a} ⇒ x ≤ {a}", f"x > {a} ∧ x ≤ {b}"],
         f"Přímý důkaz vyjde z předpokladu x > {a}, využije {a} > {b} a dojde k x > {b}: x > {a} > {b}."),
        (f"Nepřímý důkaz (x > {a}) ⇒ (x > {b}): jakou implikaci dokazujeme?",
         [f"x ≤ {b} ∧ {b} ≤ {a} ⇒ x ≤ {a}", f"x ≤ {a} ∧ {a} ≤ {b} ⇒ x ≤ {b}",
          f"x > {b} ∧ {b} > {a} ⇒ x > {a}", f"x ≤ {b} ∧ {b} > {a} ⇒ x ≤ {a}"],
         f"Vzorec x ⇒ y ⇔ ¬y ⇒ ¬x. ¬(x > {b}) je x ≤ {b} a ¬(x > {a}) je x ≤ {a}. Z x ≤ {b} ≤ {a} plyne x ≤ {a}."),
        (f"Důkaz sporem (x > {a}) ⇒ (x > {b}): jaký je předpoklad sporu a v čem je spor?",
         [f"x > {a} ∧ x ≤ {b}; z x > {a} > {b} plyne x > {b}, spor s x ≤ {b}",
          f"x ≤ {a} ∧ x > {b}; z x ≤ {a} plyne x ≤ {b}, spor s x > {b}",
          f"x > {a} ∧ x > {b}; spor vznikne dosazením x = {a + 1}",
          f"x ≤ {a} ∧ x ≤ {b}; spor nevznikne"],
         f"Předpoklad je x ∧ ¬y, tedy x > {a} ∧ x ≤ {b}. Z x > {a} > {b} vyjde x > {b}, tedy x > {b} ∧ x ≤ {b}."),
    ]


X0 = [
    ("Dokazujeme (x > 0) ⇒ (x + 2 > 2) přímo. Jak se postupuje?",
     ["z x > 0 přičteme na obou stranách 2 a dostaneme x + 2 > 2",
      "z x > 0 odečteme na obou stranách 2 a dostaneme x − 2 > 2",
      "z x > 0 vynásobíme obě strany dvěma a dostaneme 2x > 2",
      "dosadíme x = 1 a ověříme, že 3 > 2"],
     "Přičtením 2 k nerovnosti x > 0 vznikne x + 2 > 0 + 2 = 2. Dosazení jedné hodnoty nic nedokazuje."),
    ("Dokazujeme (x > 0) ⇒ (x + 2 > 2) nepřímo. Jakou implikaci dokážeme?",
     ["x + 2 ≤ 2 ⇒ x ≤ 0", "x ≤ 0 ⇒ x + 2 > 2", "x + 2 > 2 ⇒ x > 0", "x ≤ 2 ⇒ x + 2 ≤ 0"],
     "Obměna ¬y ⇒ ¬x. ¬(x + 2 > 2) je x + 2 ≤ 2 a ¬(x > 0) je x ≤ 0. Odečtením 2 z x + 2 ≤ 2 vyjde x ≤ 0."),
    ("Dokazujeme (x > 0) ⇒ (x + 2 > 2) sporem. Jaký je předpoklad a v čem je spor?",
     ["x > 0 ∧ x + 2 ≤ 2; z x + 2 ≤ 2 plyne x ≤ 0, což je spor s x > 0",
      "x ≤ 0 ∧ x + 2 > 2; z x + 2 > 2 plyne x > 0, což je spor s x ≤ 0",
      "x > 0 ∧ x + 2 > 2; spor vznikne dosazením x = 1",
      "x ≤ 0 ∧ x + 2 ≤ 2; spor nevznikne"],
     "Předpoklad x ∧ ¬y je x > 0 ∧ x + 2 ≤ 2. Odečtením 2 vyjde x ≤ 0, tedy x > 0 ∧ x ≤ 0, spor."),
]

INDUKCE = [
    ("Indukce, 1 + 2 + ... + n = n(n + 1)/2: v indukčním kroku k předpokladu přičteme k + 1 a dostaneme",
     ["k(k + 1)/2 + (k + 1) = (k + 1)(k + 2)/2", "k(k + 1)/2 + (k + 1) = k(k + 2)/2",
      "k(k + 1)/2 + k = (k + 1)(k + 2)/2", "k(k + 1)/2 + (k + 1) = (k + 1)(k + 1)/2"],
     "Základní krok: n = 1, 1 = 1 · 2 / 2. Krok: k(k + 1)/2 + (k + 1) = (k + 1)(k + 2)/2, vzorec pro n = k + 1."),
    ("Indukce, 1 + 3 + 5 + ... + (2n − 1) = n²: v indukčním kroku k předpokladu přičteme 2k + 1 a dostaneme",
     ["k² + (2k + 1) = (k + 1)²", "k² + (2k + 1) = k² + 1", "k² + (2k − 1) = (k + 1)²", "k² + 2k = (k + 1)²"],
     "Základní krok: n = 1, 1 = 1². Krok: k² + 2k + 1 = (k + 1)², vzorec pro n = k + 1."),
    ("Indukce, 2 + 4 + 6 + ... + 2n = n(n + 1): v indukčním kroku k předpokladu přičteme 2(k + 1) a dostaneme",
     ["k(k + 1) + 2(k + 1) = (k + 1)(k + 2)", "k(k + 1) + 2k = (k + 1)(k + 2)",
      "k(k + 1) + 2(k + 1) = (k + 1)(k + 1)", "k(k + 1) + (k + 1) = (k + 1)(k + 2)"],
     "Základní krok: n = 1, 2 = 1 · 2. Krok: k(k + 1) + 2(k + 1) = (k + 1)(k + 2), vzorec pro n = k + 1."),
]

# pořadí: přímý ×3, nepřímý ×3, sporem ×3, indukce ×3
_I = [ineq(5, 3), ineq(8, 2), X0]
CHOICE = [ex[m] for m in range(3) for ex in _I] + INDUKCE


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
    rnd = random.Random(5)  # pevné pořadí, aby správná odpověď nebyla pořád A
    qs = []
    for text, opts, expl in CHOICE:
        order = list(range(len(opts)))
        rnd.shuffle(order)
        qs.append({"type": "choice", "text": text,
                   "options": {"ABCD"[i]: opts[j] for i, j in enumerate(order)},
                   "correct": ["ABCD"[order.index(0)]], "explanation": expl})
    for i, q in enumerate(qs, 1):
        q["number"] = i
        q["id"] = f"2d-{i}"
    out = {"title": "Důkazy (sada na cvičení)", "lecture": 2, "date": "2026-10-08", "questions": qs}
    path = Path(__file__).parent / "banky" / "02d-dukazy.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_c = sum(q["type"] == "choice" for q in qs)
    print(f"{path.name}: {len(qs)} otázek ({n_c} výběrových, {len(qs) - n_c} na výsledek)")


if __name__ == "__main__":
    main()
