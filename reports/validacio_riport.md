# Validációs riport (2026-11-05)

**Összesített állapot: WARN**

A modell előrejelzéseinek automatikus invariáns- és konzisztencia-ellenőrzése (`validate_forecast.py`). CRITICAL hiba esetén a pipeline nem commitol és nem push-ol.

## Fázis: pre — WARN (2026-11-05T08:35:37)

| | Súlyosság | Ellenőrzés | Leírás |
|---|---|---|---|
| ✅ | CRITICAL | `factors.count` | 8 tényező a config/factors.json-ban (elvárt: 8) |
| ✅ | CRITICAL | `factors.values` | minden tényezőnek mindhárom forgatókönyv-értéke véges szám |
| ✅ | CRITICAL | `factors.alap_between` | a tényezők alap értéke a pesszimista és az optimista között van |
| ✅ | CRITICAL | `factors.band` | a tényező-sávok szimmetrikusak, és egyeznek a note-ban leírttal |
| ✅ | CRITICAL | `segments.sensitivity_range` | az érzékenységek −1..+1 között, az évjárat-súlyok pozitívak |
| ✅ | CRITICAL | `engine.count` | 48 szegmens (elvárt: 48) |
| ✅ | CRITICAL | `engine.values` | minden szegmens-pontszám véges szám |
| ✅ | CRITICAL | `engine.score_range` | minden |pontszám| ≤ 2.0 |
| ✅ | CRITICAL | `engine.drivers_sum` | a tényezőnkénti hozzájárulások összege × évjárat-súly = pontszám |
| ✅ | CRITICAL | `engine.momentum_cap` | momentum-tagok: hajtás ≤ ±0.15, márka ≤ ±0.1 |
| ✅ | CRITICAL | `engine.alap_between` | minden szegmens alap pontszáma a pesszimista és az optimista között van |
| ✅ | WARN | `sources.manual_stale` | a kézi forrásfájlok (akkuár, EV-vámok, CO2) a STALE_DAYS küszöbön belül frissültek |
| ⚠️ | WARN | `sources.top_modellek_stale` | a data/top_modellek.json 48 napos (küszöb: 45 nap) |
| ✅ | WARN | `backtest.fresh` | a backtest ma futott (generated: 2026-11-05) |
| ✅ | WARN | `backtest.quality` | a backtest korrelációja nem negatív, a találati arány legalább 50% |

## Fázis: post — PASS (2026-11-05T08:35:37)

| | Súlyosság | Ellenőrzés | Leírás |
|---|---|---|---|
| ✅ | WARN | `dashboard.fresh` | a dashboard_data.json ma készült (generated: 2026-11-05) |
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
| ✅ | WARN | `history.jumps` | nincs szokatlan ugrás az előző napi futáshoz (2026-10-09) képest |
| ✅ | CRITICAL | `history.snapshot` | a legutóbbi history-snapshot = a mostani dashboard összesítői |
| ✅ | WARN | `template.tofixed` | nincs toFixed() látható szövegben (számok csak fmt/fmtPlain/fmtInt-en át) |
| ✅ | WARN | `template.internal_text` | nincs belső karbantartási szöveg (scriptnév, launchd, Claude) a publikus oldalon |
