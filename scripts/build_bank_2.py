#!/usr/bin/env python3
"""Vygeneruje banku otázek pro 2. přednášku (výroková logika) do banky/.

Deklarace využití AI: vytvořeno s pomocí nástroje Claude Sonnet 5.5 (Anthropic, 2026),
uvedeno v souladu se Směrnicí rektora UJEP č. 7/2026 (dobrovolně).

Obsah vychází z autorových poznámek z přednášky 8. 10. 2026 a z cvika 2. Otázky na pravdivostní
hodnoty se počítají zde (ne ručně). Teoretické části je třeba kontrolovat proti sylabu KI/TIN.
Spuštění:  python3 build_bank_2.py
"""
import itertools
import json
import random
from pathlib import Path

ROWS = list(itertools.product((1, 0), repeat=2))  # 11, 10, 01, 00

OPS = {
    "¬x": lambda x, y: int(not x),
    "x ∧ y": lambda x, y: int(x and y),
    "x ∨ y": lambda x, y: int(x or y),
    "x ⇒ y": lambda x, y: int((not x) or y),
    "x ⇔ y": lambda x, y: int(x == y),
}


def col(f):
    """Sloupec pravdivostních hodnot pro řádky 11, 10, 01, 00, jako řetězec."""
    return "".join(str(int(bool(f(x, y)))) for x, y in ROWS)


# formule pro příklady na výsledek: (zápis, funkce)
FORMS = [
    ("x ∧ y", lambda x, y: int(x and y)),
    ("x ∨ y", lambda x, y: int(x or y)),
    ("x ⇒ y", lambda x, y: int((not x) or y)),
    ("y ⇒ x", lambda x, y: int((not y) or x)),
    ("x ⇔ y", lambda x, y: int(x == y)),
    ("¬x ∨ y", lambda x, y: int((not x) or y)),
    ("¬y ⇒ ¬x", lambda x, y: int(y or (not x))),
    ("¬(x ∧ y)", lambda x, y: int(not (x and y))),
    ("¬x ∨ ¬y", lambda x, y: int((not x) or (not y))),
    ("¬(x ∨ y)", lambda x, y: int(not (x or y))),
    ("¬x ∧ ¬y", lambda x, y: int((not x) and (not y))),
    ("x ∧ ¬y", lambda x, y: int(x and (not y))),
    ("(x ⇒ y) ∧ (y ⇒ x)", lambda x, y: int(((not x) or y) and ((not y) or x))),
]

# ověření vztahů, na kterých stojí výběrové otázky (skript spadne, kdyby neplatily)
assert col(lambda x, y: (not x) or y) == col(lambda x, y: y or (not x))                # implikace = obměna
assert col(lambda x, y: (not x) or y) != col(lambda x, y: (not y) or x)                # implikace != obrácení
assert col(lambda x, y: not (x and y)) == col(lambda x, y: (not x) or (not y))         # De Morgan 1
assert col(lambda x, y: not (x or y)) == col(lambda x, y: (not x) and (not y))         # De Morgan 2
assert col(lambda x, y: x == y) == col(lambda x, y: ((not x) or y) and ((not y) or x))  # ekvivalence
assert all((x or (not x)) for x, _ in ROWS)                                           # x ∨ ¬x tautologie
assert col(lambda x, y: (not x) or y) != col(lambda x, y: (not x) or (not y))          # inverze není ekvivalentní


def table(expr, f):
    lines = ["x y | " + expr, "----+" + "-" * (len(expr) + 1)]
    for x, y in ROWS:
        lines.append(f"{x} {y} | {int(bool(f(x, y)))}")
    return "\n".join(lines)


# (text, [možnosti], [správné indexy], vysvětlení)
CHOICE = [
    ("Co je výrok?",
     ["věta, které lze přiřadit právě jednu pravdivostní hodnotu", "jakákoli oznamovací věta",
      "věta obsahující proměnnou", "věta, která je vždy pravdivá"], [0],
     "Výrok je věta určitého jazyka, které lze přiřadit právě jednu z hodnot pravda (1) / nepravda (0)."),
    ("Která z vět je výrok?",
     ["4 je sudé", "Bude pršet", "x > 0", "Zavři dveře"], [0],
     "„4 je sudé“ má právě jednu hodnotu (pravda). „Bude pršet“ se na přednášce označilo jako ne-výrok (hodnotu nelze určit), „x > 0“ je výroková forma."),
    ("Jakou pravdivostní hodnotu má věta „3 je sudé“?", ["1", "0", "nelze určit", "není výrok"], [1],
     "3 není sudé, je to výrok s hodnotou 0."),
    ("Kdy je konjunkce x ∧ y pravdivá?",
     ["když jsou pravdivé oba výroky", "když je pravdivý aspoň jeden výrok", "když jsou oba nepravdivé",
      "když mají výroky různou hodnotu"], [0], "Konjunkce („a“) je pravdivá jen když platí x i y."),
    ("Kdy je disjunkce x ∨ y nepravdivá?",
     ["když jsou oba výroky nepravdivé", "když je nepravdivý aspoň jeden", "když jsou oba pravdivé",
      "nikdy"], [0], "Disjunkce („nebo“) je nepravdivá jen v řádku x = 0, y = 0."),
    ("Kdy je implikace x ⇒ y nepravdivá?",
     ["jen když x = 1 a y = 0", "jen když x = 0 a y = 1", "když jsou x i y nepravdivé", "když jsou x i y pravdivé"], [0],
     "Z pravdy nesmí plynout nepravda: x ⇒ y je 0 jen pro (1, 0), ve všech ostatních řádcích je 1."),
    ("Kdy je ekvivalence x ⇔ y pravdivá?",
     ["když mají x a y stejnou pravdivostní hodnotu", "když je aspoň jedno z nich pravdivé",
      "když je x pravdivé a y nepravdivé", "vždy"], [0], "Ekvivalence je 1 pro (1,1) a (0,0)."),
    ("Jak zní obměna implikace x ⇒ y?",
     ["¬y ⇒ ¬x", "y ⇒ x", "¬x ⇒ ¬y", "¬x ⇒ y"], [0],
     "Obměna je ¬y ⇒ ¬x. Obrácení je y ⇒ x, to s původní implikací ekvivalentní není."),
    ("Mají implikace x ⇒ y a její obměna stejnou pravdivostní hodnotu?",
     ["ano, vždy", "ne, nikdy", "jen když je x pravdivé", "jen když je y pravdivé"], [0],
     "Ano, x ⇒ y ≡ ¬y ⇒ ¬x. Je to důležité tvrzení z přednášky."),
    ("Mají implikace x ⇒ y a její obrácení y ⇒ x vždy stejnou pravdivostní hodnotu?",
     ["ne, nemusí", "ano, vždy", "ano, pokud je x pravdivé", "ano, pokud je y nepravdivé"], [0],
     "Liší se v řádcích (1,0) a (0,1). Obrácení implikace nemusí mít stejnou hodnotu."),
    ("Které tři způsoby důkazu implikace x ⇒ y se probíraly?",
     ["přímý, nepřímý (obměnou), sporem", "přímý, grafický, numerický", "sporem, indukcí, výčtem",
      "tabulkou, grafem, slovně"], [0],
     "1) přímý (řetěz implikací), 2) nepřímý (obměnou), 3) sporem."),
    ("Jak vypadá přímý důkaz implikace x ⇒ y?",
     ["řetěz implikací x ⇒ y₁, y₁ ⇒ y₂, ..., yₙ ⇒ y", "dokazuje se ¬y ⇒ ¬x",
      "předpokládá se x ∧ ¬y a hledá se spor", "dosadí se všechny hodnoty do tabulky"], [0],
     "Přímý důkaz je řetěz implikací od předpokladu k závěru."),
    ("Co se dokazuje při nepřímém důkazu implikace x ⇒ y?",
     ["její obměna ¬y ⇒ ¬x", "její obrácení y ⇒ x", "negace ¬x", "ekvivalence x ⇔ y"], [0],
     "Dokáže se obměna ¬y ⇒ ¬x, která je s implikací ekvivalentní."),
    ("Jak se postupuje při důkazu sporem implikace x ⇒ y?",
     ["předpokládá se x ∧ ¬y, z toho se odvodí nepravdivé tvrzení Z", "předpokládá se y a odvodí se x",
      "předpokládá se ¬x ∧ y", "sestaví se pravdivostní tabulka"], [0],
     "(x ∧ ¬y) ⇒ Z, kde Z je nepravda; předpoklad „x platí a y ne“ tedy neplatí."),
    ("Co musíme dokázat, když dokazujeme ekvivalenci x ⇔ y?",
     ["obě implikace x ⇒ y a y ⇒ x", "jen x ⇒ y", "jen ¬y ⇒ ¬x", "x ∧ y"], [0],
     "(x ⇔ y) ⇔ (x ⇒ y) ∧ (y ⇒ x)."),
    ("Co je výroková formule?",
     ["zápis z písmen, logických spojek a závorek, z něhož se po dosazení výroků stane výrok",
      "věta s proměnnou, která se stane výrokem po dosazení čísla", "věta, která je vždy pravdivá",
      "množina všech pravdivých výroků"], [0],
     "Výroková formule: písmena + logické spojky + závorky; po dosazení výroků za písmena vznikne výrok."),
    ("Co je tautologie?",
     ["formule, která je po dosazení jakýchkoli hodnot vždy pravdivá", "formule, která je vždy nepravdivá",
      "formule s aspoň jednou spojkou", "formule se stejnými písmeny jako jiná formule"], [0],
     "Tautologie dává při libovolném dosazení vždy pravdivý výrok."),
    ("Která formule je tautologie?",
     ["x ∨ ¬x", "x ∧ ¬x", "x ⇒ ¬x", "x ∧ y"], [0],
     "x ∨ ¬x je pravdivé pro x = 1 i x = 0. Ostatní jsou pro nějaké dosazení nepravdivé."),
    ("Kdy jsou dvě výrokové formule ekvivalentní?",
     ["obsahují stejná písmena a po dosazení mají vždy stejnou pravdivostní hodnotu",
      "obsahují stejné spojky", "mají stejný počet písmen", "jsou obě tautologie"], [0],
     "Ekvivalentní formule: stejná písmena a po jakémkoli dosazení vždy stejná pravdivostní hodnota."),
    ("Čemu je ekvivalentní ¬(x ∧ y)? (De Morganův zákon)",
     ["¬x ∨ ¬y", "¬x ∧ ¬y", "x ∨ y", "¬x ⇒ y"], [0],
     "¬(x ∧ y) ≡ ¬x ∨ ¬y; tabulkou vyjde (0,1,1,1) na obou stranách."),
    ("Čemu je ekvivalentní ¬(x ∨ y)? (De Morganův zákon)",
     ["¬x ∧ ¬y", "¬x ∨ ¬y", "x ∧ y", "x ⇒ y"], [0],
     "¬(x ∨ y) ≡ ¬x ∧ ¬y; tabulkou vyjde (0,0,0,1) na obou stranách."),
    ("Co je výroková forma?",
     ["věta určitého jazyka obsahující proměnnou, např. V(x)", "věta bez proměnné", "formule bez spojek",
      "libovolný pravdivý výrok"], [0],
     "Výroková forma obsahuje proměnnou (nebo několik); výrokem se stane po dosazení z definičního oboru."),
    ("Je věta „x² + y² = 1“ výrok?",
     ["ne, je to výroková forma; výrokem se stane po dosazení za x a y", "ano, je vždy pravdivá",
      "ano, je vždy nepravdivá", "ne, je to tautologie"], [0],
     "Obsahuje proměnné, takže je to forma; po dosazení vhodných prvků z definičního oboru vznikne výrok."),
    ("Co je definiční obor výrokové formy V(x)?",
     ["množina D, pro jejíž každé c je V(c) výrok", "množina c, pro která je V(c) pravdivé", "množina všech hodnot x",
      "prázdná množina"], [0],
     "Definiční obor: V(c) je výrok pro každé c ∈ D (pravdivý nebo nepravdivý)."),
    ("Co je obor pravdivosti výrokové formy V(x)?",
     ["množina c z definičního oboru, pro která je V(c) pravdivý výrok", "celý definiční obor",
      "množina c, pro která je V(c) nepravdivé", "množina hodnot funkce"], [0],
     "Obor pravdivosti je podmnožina definičního oboru s pravdivým V(c). Pro √x = 5, D: x ≥ 0 je to {25}."),
    ("Co znamená zápis a ∈ X?",
     ["a je prvkem množiny X", "a není prvkem množiny X", "a je podmnožinou X", "a je rovno X"], [0],
     "∈ čteme „je prvkem“, ∉ čteme „není prvkem“."),
    ("Jak se při negaci mění kvantifikátory?",
     ["∀ → ∃ a ∃ → ∀, negace se přesune dovnitř", "zůstanou stejné", "∀ → ∀, ∃ → ∃, jen se přidá ¬",
      "∃ se změní na ∃!"], [0],
     "¬(∀x V(x)) ⇔ ∃x ¬V(x) a ¬(∃x V(x)) ⇔ ∀x ¬V(x)."),
    ("Čemu je ekvivalentní ¬(∀x ∈ U; V(x))?",
     ["∃x ∈ U; ¬V(x)", "∀x ∈ U; ¬V(x)", "∃x ∈ U; V(x)", "¬(∃x ∈ U; V(x))"], [0],
     "Neplatí, že V platí pro všechna x, právě když existuje x, pro které V neplatí."),
    ("Čemu je ekvivalentní ¬(∃x ∈ U; V(x))?",
     ["∀x ∈ U; ¬V(x)", "∃x ∈ U; ¬V(x)", "∀x ∈ U; V(x)", "∃!x ∈ U; V(x)"], [0],
     "Neexistuje x s V(x), právě když pro všechna x platí ¬V(x)."),
    ("Co znamená kvantifikátor ∃!?",
     ["existuje právě jeden prvek", "existuje aspoň jeden prvek", "pro každý prvek", "neexistuje žádný prvek"], [0],
     "∃! je kvantifikátor jednoznačné existence. Příklad: ∃!x ∈ ℝ; x = 5."),
    ("Je výrok „∀x ∈ ℝ; x² ≥ 0“ pravdivý?", ["ano", "ne", "jen pro kladná x", "není výrok"], [0],
     "Druhá mocnina reálného čísla je vždy nezáporná."),
    ("Čím začíná logická výstavba matematiky?",
     ["axiomy, o kterých předpokládáme, že platí", "větami, které se dokazují", "definicemi všech pojmů",
      "lemmaty"], [0], "Na počátku jsou axiomy; předpokládáme jejich platnost."),
    ("Co jsou věty v logické výstavbě matematiky?",
     ["pravdivé výroky odvoditelné pravidly logiky z axiomů nebo dříve dokázaných vět",
      "předpoklady, které se nedokazují", "pojmy, které se nedefinují", "definice nových pojmů"], [0],
     "Věta je pravdivý výrok, který lze odvodit pomocí pravidel logiky z axiomů nebo z předcházejících vět."),
    ("Co je lemma?",
     ["věta, která se dokazuje, ale slouží spíš jako pomocná pro důkaz dalších vět", "axiom", "primitivní pojem",
      "definice"], [0], "Lemma je pomocná věta; rozdíl proti větě bývá nevýrazný."),
    ("Které pojmy se v axiomech nedefinují (primitivní pojmy)?",
     ["např. bod, přímka, čas, hmotnost", "např. rychlost a zrychlení", "např. věta a lemma", "všechny pojmy se definují"], [0],
     "Primitivní pojmy se nedefinují; další pojmy (rychlost, zrychlení) se zavádějí pomocí definic."),
]


def main():
    qs = []
    rnd = random.Random(4)  # pevné pořadí, aby správná odpověď nebyla pořád A
    for text, opts, correct, expl in CHOICE:
        order = list(range(len(opts)))
        rnd.shuffle(order)
        opts = [opts[i] for i in order]
        correct = sorted(order.index(c) for c in correct)
        qs.append({"type": "choice", "text": text,
                   "options": {"ABCD"[i]: o for i, o in enumerate(opts)},
                   "correct": ["ABCD"[i] for i in correct], "explanation": expl})
    for expr, f in FORMS:
        ans = col(f)
        sol = (f"Hodnoty pro řádky (x,y) = 11, 10, 01, 00:\n{table(expr, f)}\n"
               f"Odpověď čti shora dolů: {ans}")
        qs.append({"type": "input", "text": f"Pravdivostní hodnoty formule {expr} pro řádky (x,y) = 11, 10, 01, 00",
                   "hint": "čtyři cifry bez mezer, např. 0110", "answer": ans, "solution": sol})
    # příklady z cvika 2 (číselné soustavy z 1. přednášky)
    cviko = [("1001101", 2, 10), ("111", 8, 10), ("111", 16, 10), ("132", 10, 2)]
    SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    for s, frm, to in cviko:
        n = int(s, frm)
        ans = str(n) if to == 10 else bin(n)[2:]
        if frm == 10 and to == 2:
            m, lines = n, ["dělení      podíl  zbytek"]
            while m:
                lines.append(f"{m:>5} : 2  {m // 2:>5}  {m % 2}")
                m //= 2
            lines.append(f"Zbytky zdola nahoru: {ans}")
            sol = "\n".join(lines)
        elif frm == 10:
            sol = " + ".join(f"{c}·10^{len(s) - 1 - i}" for i, c in enumerate(s)) + f" = {n}"
        else:
            sol = " + ".join(f"{c}·{frm}^{len(s) - 1 - i}" for i, c in enumerate(s)) + f" = {n}"
        qs.append({"type": "input", "text": f"({s}){str(frm).translate(SUB)} → (?){str(to).translate(SUB)} (cvičení 8. 10.)",
                   "hint": f"výsledek v soustavě o základu {to}", "answer": ans, "solution": sol})
    for i, q in enumerate(qs, 1):
        q["number"] = i
        q["id"] = f"2-{i}"
    out = {"title": "Výroková logika, kvantifikátory a výstavba matematiky", "lecture": 2, "date": "2026-10-08",
           "questions": qs}
    path = Path(__file__).parent / "banky" / "02-2026-10-08.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_c = sum(q["type"] == "choice" for q in qs)
    print(f"{path.name}: {len(qs)} otázek ({n_c} výběrových, {len(qs) - n_c} na výsledek)")


if __name__ == "__main__":
    main()
