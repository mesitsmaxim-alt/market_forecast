# Validációs riport (2026-11-12)

**Összesített állapot: PASS**

A modell előrejelzéseinek automatikus invariáns- és konzisztencia-ellenőrzése (`validate_forecast.py`). CRITICAL hiba esetén a pipeline nem commitol és nem push-ol.

## Fázis: post — PASS (2026-11-12T09:01:52)

| | Súlyosság | Ellenőrzés | Leírás |
|---|---|---|---|
| ✅ | WARN | `dashboard.fresh` | a dashboard_data.json ma készült (generated: 2026-11-12) |
| ✅ | CRITICAL | `dashboard.segments_count` | 48 szegmens, 48 egyedi kombináció (elvárt: 48) |
| ✅ | CRITICAL | `dashboard.factors_count` | 8 tényező (elvárt: 8) |
| ✅ | CRITICAL | `dashboard.coverage` | lefedettség: 5 automata + 3 kézi = 8 tényező |
| ✅ | CRITICAL | `dashboard.values` | minden pontszám véges szám |
| ✅ | CRITICAL | `dashboard.alap_between` | az alap pontszám a pesszimista és az optimista között van (szegmensek, összesítők) |
| ✅ | CRITICAL | `dashboard.drivers_sum` | a drivers pontjainak összege = pontszám × 100 (szegmensek, összesítők) |
| ✅ | CRITICAL | `dashboard.dir_labels` | minden irány-címke = classify(pontszám) |
| ✅ | CRITICAL | `dashboard.market_weights` | a piaci súlyok évjárat-sávonként nemnegatívak és 1-re összegződnek |
| ✅ | CRITICAL | `consistency.factors` | a dashboard tényező-értékei = config/factors.json |
| ✅ | CRITICAL | `consistency.backtest` | a dashboard módszertani blokkjának backtest-eredménye = data/backtest.json |
| ✅ | CRITICAL | `consistency.fuel_headline` | üzemanyagár: a főszám = a sparkline utolsó pontja |
| ✅ | CRITICAL | `forecast.cards` | 13 trendvetítés-kártya: azonos hossz, alsó ≤ pont ≤ felső |
| ✅ | CRITICAL | `forecast.share_range` | a részesedés-vetítések 0–100% között maradnak |
| ✅ | WARN | `history.jumps` | nincs szokatlan ugrás az előző napi futáshoz (2026-11-10) képest, vagy van rá módszertani bejegyzés |
| ✅ | CRITICAL | `history.snapshot` | a legutóbbi history-snapshot = a mostani dashboard összesítői |
| ✅ | WARN | `template.tofixed` | nincs toFixed() látható szövegben (számok csak fmt/fmtPlain/fmtInt-en át) |
| ✅ | WARN | `template.internal_text` | nincs belső karbantartási szöveg (scriptnév, launchd, Claude) a publikus oldalon |
