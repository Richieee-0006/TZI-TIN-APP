# Graph Report - tzi-trener  (2026-10-29)

## Corpus Check
- 19 files · ~105,071 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 2 file(s) not represented in the graph (top: (none) 2)

## Summary
- 182 nodes · 287 edges · 10 communities (9 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c3c4f118`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- tzi_trener.py
- build_bank_3.py
- build_bank_4.py
- TZI Trenér
- test_doplnovacka.js
- json
- TZI Trenér
- TZI Trenér: plán do budoucna
- .do_GET
- El

## God Nodes (most connected - your core abstractions)
1. `El` - 10 edges
2. `Handler` - 8 edges
3. `Handler` - 8 edges
4. `TZI Trenér` - 8 edges
5. `main()` - 6 edges
6. `input_questions()` - 6 edges
7. `main()` - 6 edges
8. `main()` - 5 edges
9. `set_questions()` - 5 edges
10. `main()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `json`  [EXTRACTED]
  build_bank_2.py →   _Bridges community 1 → community 7_
- `is_partition()` --calls--> `itertools`  [EXTRACTED]
  build_bank_4.py →   _Bridges community 3 → community 1_
- `write()` --calls--> `json`  [EXTRACTED]
  build_bank_4.py →   _Bridges community 3 → community 7_
- `load_banks()` --calls--> `json`  [EXTRACTED]
  zaloha/tzi_trener_v1.py →   _Bridges community 0 → community 7_

## Import Cycles
- None detected.

## Communities (10 total, 1 thin omitted)

### Community 0 - "tzi_trener.py"
Cohesion: 0.13
Nodes (10): Handler, host_ok(), lan_ip(), list_sources(), load_banks(), load_progress(), load_questions(), main() (+2 more)

### Community 1 - "build_bank_3.py"
Cohesion: 0.21
Nodes (9): col(), main(), table(), fmt(), main(), pick_sets(), rel_props(), relation_questions() (+1 more)

### Community 3 - "build_bank_4.py"
Cohesion: 0.21
Nodes (9): build(), choice_questions(), classify(), input_questions(), is_mapping(), is_partition(), main(), set_partitions() (+1 more)

### Community 4 - "TZI Trenér"
Cohesion: 0.15
Nodes (12): Banky otázek, Desktop, Doplňovačka (na paměť), Legacy (starý vzhled), Licence, Mobil (`--lan`), Režimy, Screenshoty (+4 more)

### Community 5 - "test_doplnovacka.js"
Cohesion: 0.06
Nodes (30): AND, assert, byText(), C52, cases, choices, ctx, docOn (+22 more)

### Community 7 - "json"
Cohesion: 0.16
Nodes (12): arit(), base(), ineq(), main(), self_check(), groups(), main(), num() (+4 more)

### Community 8 - "TZI Trenér"
Cohesion: 0.40
Nodes (4): Nová přednáška, Pravidla, Soubory, TZI Trenér

### Community 9 - "TZI Trenér: plán do budoucna"
Cohesion: 0.40
Nodes (4): Až bude čas, Nápady, Opravit dřív, TZI Trenér: plán do budoucna

### Community 10 - ".do_GET"
Cohesion: 0.12
Nodes (13): Handler, host_ok(), lan_ip(), list_sources(), load_banks(), load_progress(), load_questions(), load_recall() (+5 more)

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `El` connect `El` to `test_doplnovacka.js`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Should `tzi_trener.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12962962962962962 - nodes in this community are weakly interconnected._
- **Should `test_doplnovacka.js` be split into smaller, more focused modules?**
  _Cohesion score 0.057057057057057055 - nodes in this community are weakly interconnected._
- **Should `.do_GET` be split into smaller, more focused modules?**
  _Cohesion score 0.1206896551724138 - nodes in this community are weakly interconnected._