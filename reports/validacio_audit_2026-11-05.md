# Validációs audit — 2026-11-05

**Végső ítélet: WARN**

**Publikálási javaslat:** A modell helyesen számol: mind a 8 tényező független újraszámolása egyezik, 1707/1707 egységteszt sikeres, CRITICAL invariáns-hiba nincs. A fő hajtásirányok robusztusak. A dashboard publikálható. A két CRITICAL-ként jelzett predikciós találat dokumentált, a nyilvános oldalon is kimondott korlát, ezért WARN-ra soroltam (ld. lent). A felsorolt teendőket érdemes a következő hónapokban elvégezni.

A vizsgált build: `dashboard/dashboard_data.json`, `generated` = 2026-11-05 (a mai pipeline-futás, commit `e9a5e21`).

## Determinisztikus ellenőrzés

`python3 validate_forecast.py --stage all` eredménye: **pre: WARN, post: PASS**. Részletek: [validacio_riport.md](validacio_riport.md).

Egyetlen bukott ellenőrzés: `sources.top_modellek_stale`. A `data/top_modellek.json` 48 napos, a küszöb 45 nap.

## Ítéletek

| Terület | Agent | Agent verdikt | Területi ítélet |
|---|---|---|---|
| A. Modell | invariant-checker | WARN | **WARN** |
| | calibration-auditor | WARN | |
| B. Predikciók | stats-reviewer | WARN | **WARN** |
| | prediction-tracker | FAIL → WARN (lejjebb sorolva) | |
| C. Feltételezések | source-verifier | WARN | **WARN** |
| | assumption-stress-tester | WARN | |
| | plausibility-reviewer | WARN | |

## A. Modell — helyesen számol-e?

**Igen.** Mind a 8 tényező alap értéke és sávja egyezik a független újraszámolással (az eltérés ≤ 0,05). A `compute_segments`, a momentum-sapkák, a `classify` és a `linreg_forecast` szintetikus tesztjei hibátlanok. Számítási hiba nincs. A figyelmeztetések módszertaniak: a tényezők skálái nem összemérhetők, és a CO2-tényező mást mér, mint a többi.

| tényező | alap (config) | alap (független) | sáv (config) | sáv (független) |
|---|---|---|---|---|
| oil_price | 15,5 | 15,53 | ±12,3 | 12,27 |
| battery_cost | −8,0 | −8,0 | ±6 (fix) | ±6 |
| charging_infra | 5,7 | 5,67 | ±11,0 | 11,05 |
| ev_tariffs | −1,0 | −1,0 | ±10 (fix) | ±10 |
| co2_regulation | 14,9 | 14,93 | ±4 (fix) | ±4 |
| financing_cost | −1,0 | −1,0 | ±3,6 | 3,62 |
| consumer_sentiment | 8,7 | 8,73 | ±10,5 | 10,50 |
| purchasing_power | 1,7 | 1,7 | ±4,9 | 4,86 |

### WARN

- **A top_modellek.json elavult.** Forrás: invariant-checker, source-verifier.
  - Bizonyíték: `updated` = 2026-09-18, az adat a január–augusztusi cikket tükrözi. A jarmuipar.hu 2026-10-13-án megjelentette a január–szeptemberi Top 100-at (https://www.jarmuipar.hu/2026/10/top-100-ezek-nyertesek-az-autopiacon/). Az új adatok: 129 949 db, +10,6%.
  - Teendő:
    - a jelenlegi listát áttenni a `previous` blokkba;
    - a `rows` tömböt az új cikkből kitölteni;
    - beállítani: `period_label` „2026. január–szeptember”, `market_total_units` 129949, `increment_label` „szept.”.
- **A skálák nem összemérhetők** (`engine.py:199`). Forrás: calibration-auditor.
  - Bizonyíték: minden delta /100, ezért 1 pp kamat ugyanannyit nyom, mint 1% üzemanyagár. A BEV-pontszámhoz a `financing_cost` és a `purchasing_power` alap hozzájárulása egyaránt +0,005, az `oil_price`-é +0,124. A kamat és a vásárlóerő így gyakorlatilag nem hat.
  - Teendő: z-score normalizálás, vagy a módszertani blokkban kimondani, hogy ez a két tényező elhanyagolható súlyú.
- **A co2_regulation szint, nem változás** (`calibrate_factors.py:330-351`). Forrás: calibration-auditor.
  - Bizonyíték: `pressure = reduction_pct / years_left` = 47,1 / 3,157 = 14,93. Ez az évente szükséges csökkentés, nem a következő 12 hónap elmozdulása. A határidő közeledtével mechanikusan nő, a ±4-es sávnak pedig nincs empirikus alapja.
  - Teendő: eldönteni és dokumentálni, hogy szint vagy delta.

### INFO

- **Az oil_price alapja még le nem zárt hétből számol.** A 2026-11-02–08-i heti átlagot veti össze az egy évvel korábbi teljes héttel. A különbség elhanyagolható.
- **A purchasing_power alapja és sávja más sorozatból jön.** Az alap a reáljövedelemből (+1,7), a sáv a reálkereset szórásából számol. A reálkereset 2025-ben +4,8 lett volna.
- **Az EAFO-export 2026-09-14-i.** A 2026 Q3 azóta lezárult, ezért új kézi export kell.
- **A linreg_forecast None-kezelése torzítana.** A dashboard sorozataiban jelenleg nincs None, így a torzítás nem érvényesül.
- **Elírás a backtest.py docstringjében.** „3 tényezőt” említ, a kód 4-et használ.

## B. Predikciók — bejön-e, amit mond?

**Részben.** A 10-09-i naiv átállás a friss adaton is megáll. Az alapkamat, az EUR/HUF, a két szentiment- és a két bér/jövedelem-kártya lefedettsége 66–74%, a névleges ~68%. A backtest szövege őszinte: egyik összevetés sem szignifikáns, és a szöveg ezt mondja. Gyenge pont a tényezők „a trend folytatódik” feltevése és néhány lineáris kártya: a töltőinfra-kártya, amely már rosszabb a naivnál, és a forgalomba helyezési kártya, amely nem kezeli a szezonalitást.

| vetítés | n | MAE / naiv (RW) | lefedettség |
|---|---|---|---|
| alapkamat (naiv) | 153 | 1,00× | 67% (utolsó 40: 30%) |
| EUR/HUF (naiv) | 1359 | 1,00× | 67% |
| vásárlási szándék / fogyasztói bizalom (naiv) | 2361 | 1,00× | 74% |
| reálkereset / reáljövedelem (naiv) | 59 | 1,00× | 73% / 66% |
| töltőinfra (lineáris) | 62 | **1,44×** | 55% |
| forgalomba helyezés (lineáris) | 30 | 0,90× | 43% |
| részesedés benzin / dízel | 33 | 0,41× / 0,97× | 45% / 36% |
| részesedés hibrid / elektromos | 33 | 0,68× / 0,83× | **18% / 12%** |
| részesedés egyéb | 33 | **2,04×** | 70% |

| tényező-feltevés | MAE perzisztencia / nulla | irány-találat |
|---|---|---|
| consumer_sentiment | 1,60× (utolsó 60: 1,86×) | 47% |
| financing_cost | 1,33× | 59% |
| oil_price | 1,31× | 51% |
| purchasing_power | 0,80–0,87× | 63–77% |

Backtest (n=23): BEV vs ICE találati arány 61% (p=0,41), korreláció +0,15 (p=0,51). Hibrid vs ICE találati arány 52% (p=1,0), korreláció +0,17 (p=0,45). Egyik sem szignifikáns.

### WARN

- **A „folytatódik a trend” tényező-feltevés három tényezőnél gyengébb a nullánál.** Forrás: prediction-tracker (CRITICAL-ként jelezte, lejjebb sorolva, ld. lent).
  - Bizonyíték: consumer_sentiment 1,60× (n=372, az utolsó 60 vágáson 1,86×, irány 20%), financing_cost 1,33×, oil_price 1,31×. Ugyanez volt a 10-09-i audit megállapítása is, azóta nem történt döntés.
  - Teendő: az alap értéket a 0 felé húzni. 50%-os perzisztencia mellett a szentiment MAE-je 14,4 → 11,2. Ez a modell központi feltevését érinti, ezért külön döntést igényel.
- **A hibrid és az elektromos részesedés sávja szűk.** Forrás: prediction-tracker (CRITICAL-ként jelezte, lejjebb sorolva), stats-reviewer.
  - Bizonyíték: a lefedettség 18%, illetve 12%. A pont viszont jobb a naivnál (0,68×, 0,83×), és az irány 91% / 85%. A trend tehát jó, a sáv a probléma.
  - Teendő: ezeknél a kártyáknál kb. 2σ-s sáv, vagy csak az irány megjelenítése.
- **A töltőinfra-kártya rosszabb a random walknál.** Forrás: prediction-tracker.
  - Bizonyíték: MAE 1,44× (h=1: 1,63×, h=2: 1,51×), lefedettség 55%. A CLAUDE.md „0,82×” állítása már nem igaz. A vetítés 4 negyedév alatt +18%-ot ad (6469), a tényleges ütem ~124 db/negyedév, a meredekség 207.
  - Teendő: naiv kártya vagy rövidebb ablak (walk-forward teszttel eldönteni), és a CLAUDE.md frissítése.
- **A forgalomba helyezési vetítés nem kezeli a szezonalitást.** Forrás: stats-reviewer.
  - Bizonyíték: 8 pontos OLS, a 4. negyedévre 86 177 db, a történeti maximum 78 118. Az alsó sávhatár nem monoton.
  - Teendő: szezonálisan igazított vagy YoY-naiv modell, esetleg rövidebb horizont. A minta kicsi (n=30), a KSH 2026 Q3 adat után újraértékelni.
- **Az alapkamat-kártya felirata pontatlan, a sávja szűk.** Forrás: prediction-tracker.
  - Bizonyíték: a sorozat csak a kamatváltoztatásokat tartalmazza, ezért a felirat valójában „következő kamatváltoztatás”. A mean-mentes szórásból számolt sáv az utolsó 40 vágáson csak 30%-ot fed le, mert a lépések egyirányúak.
  - Teendő: a felirat pontosítása, és RMS-alapú sáv.
- **Az „egyéb” részesedés-kártya 2,04×-szer rosszabb a naivnál.** Forrás: prediction-tracker.
  - Teendő: elhagyni vagy naivra cserélni.

### INFO

- **Az ex-post ellenőrzés még nem lehetséges.** A gyűjtés 2026-09-18 óta tart, és azóta nem érkezett új valós adatpont: a forgalomba helyezés utolsó negyedéve 2026 Q2, az Eurostat-adat 2025-ig tart. Az első értékelés a KSH 2026 Q3 adat után végezhető el.
- **A napi pillanatképekben az irányok stabilak.** 6 nap alapján a BEV pontszáma 0,29–0,37, a PHEV/HEV pozitív, az ICE negatív. Az ICE −0,130 → −0,158 elmozdulását valós inputváltozás okozta: az oil_price 12,9 → 15,5, a szentiment 11,6 → 8,7.
- **A backtest szűk vetületet validál.** Egyidejű összefüggést mér, nem előrejelzést, csak hajtás-érzékenységgel dolgozik, és más proxykat használ. Ez dokumentált korlát, a riport szövege kimondja.

## C. Feltételezések — igazak és robusztusak-e?

**Az irányok igen, a finom címkék és rangsorok nem.** A kézi források naprakészek, kivéve a top-modellek listát. A 8 aggregátum előjele 500 véletlen perturbációból mindegyikben megmarad (seed 42), és egyetlen együttható ±2,0-ig tolva sem fordít meg előjelet. Az „Erős növekedés” és a „Növekedés” közötti címke viszont sok aggregátumnál küszöbközeli, a HEV/PHEV sorrend és a márkarangsor pedig véletlenszerű.

| aggregátum | alap | előjel-stabilitás | címke-stabilitás |
|---|---|---|---|
| ICE | −0,158 | 100% | 69% |
| HEV | +0,164 | 100% | 79% |
| PHEV | +0,170 | 100% | 89% |
| BEV | +0,328 | 100% | 100% |
| tömeggyártó | +0,140 | 100% | 72% |
| prémium | +0,147 | 100% | 59% |
| budget | +0,060 | 100% | 75% |
| kínai belépő | +0,157 | 100% | 68% |

Rangsorstabilitás: a hajtás-rangsor 59%-ban, a márka-rangsor 35%-ban változatlan.

### WARN

- **Az egyszerű átlag és a piacsúlyozott érték előjele eltér.** Forrás: plausibility-reviewer, assumption-stress-tester.
  - Bizonyíték: budget +0,060 vs −0,053, idősebb használt +0,050 vs −0,085. A tömeggyártó és a prémium piacsúlyozott értéke ≈ +0,03, és a `consumer_sentiment` elhagyásával előjelet vált.
  - Teendő: a `conclBrand` és a `conclYear` említse a piacsúlyozott előjelet is, a ±0,05 alatti piacsúlyozott értéket pedig „semleges tartomány”-ként kezelje.
- **A címkék küszöbközeliek, a rangsorok nem robusztusak.** Forrás: assumption-stress-tester, plausibility-reviewer.
  - Bizonyíték: 6 aggregátum a `classify()`-küszöbtől 0,02-n belül van. A HEV és a PHEV különbsége 0,006, holott a valós trend a HEV-et mutatja erősebbnek (+5,1 vs +0,6 pp/év).
  - Teendő: a szövegek ne finom kategóriát állítsanak, és ne rangsoroljanak HEV/PHEV vagy a márkakategóriák között.
- **Két tényező viszi a kimenetet: oil_price és co2_regulation.** Forrás: assumption-stress-tester.
  - Bizonyíték: a tornado első 10 helyéből 8 az `oil_price`-é, 2 a `co2_regulation`-é. Az `oil_price` elhagyásával az ICE −0,158-ról −0,061-re változik, 4 címke vált.
  - Teendő: jelölni, hogy ezek illusztratív becslések, és megfontolni az `oil_price` YoY simítását.

### INFO

- **co2_szabalyozas.json:** a 2035-ös (−90%) lazítás még csak javaslat. Az ipari bizottság megszavazta, az ENVI-szavazás november elején, a plenáris decemberben várható. A `proposals` kezelése helyes.
- **ev_vamok.json:** a 2026-02-10-i VW Anhui döntés óta nincs újdonság.
- **akkuar.json:** a BNEF 2025-ös adata (108 USD/kWh, −8%) megerősítve, a következő frissítés decemberben esedékes. A `source_url` útvonala (`clean-transport` vs `clean-energy`) ellenőrizendő.
- **A momentum nem hoz létre irányt.** Momentum nélkül is ugyanazok az előjelek jönnek ki, csak gyengébb címkékkel.
- **Az idősebb használtak oil_price-érzékenysége kétszer számolódhat.** Az `idosebb_hasznalt` `extra_sensitivity.oil_price` −0,2 az ICE −0,9-éhez adódik. Felülvizsgálandó.
- **A szentiment szövege félrevezető lehet.** A vásárlási szándék szintje negatív (−12,9), csak javult. A szöveg „javuló”-t mondjon, ne „pozitívat”.
- **A „Mi változott?” blokk túlhangsúlyozhat.** A prémium és a tömeggyártó irányváltása küszöb közeli, ≤0,03-os elmozdulás, a blokk ne emelje ki jelentős eseményként.

## Lejjebb sorolt találatok

- **[CRITICAL → WARN] consumer_sentiment perzisztencia** (prediction-tracker). Nem számítási hiba, hanem a modell dokumentált központi feltevése. A dashboard módszertani blokkja kimondja: „a legfrissebb megfigyelt trendből, azzal a feltételezéssel, hogy folytatódik”. A 10-09-i audit ugyanezt a számot (1,60×) WARN-ként, külön döntést igénylő teendőként rögzítette. Új bizonyíték nem merült fel, csak az utolsó 60 vágás romlott (1,86×). A probléma valós, és a teendőlistán az első helyen marad.
- **[CRITICAL → WARN] hibrid/elektromos sávlefedettség** (prediction-tracker). A CLAUDE.md dokumentálja („12–27%, mert a lineáris trend ott tartósan alulbecsül”), és a nyilvános Előrejelzés fül is kimondja („A gyorsuló részesedéseknél (hibrid, elektromos) a lineáris trend inkább alulbecsül”). Az agent maga is nyilvános, kimondott korlátnak nevezte.
- **[WARN → INFO] momentum-dominancia** (plausibility-reviewer). A stress-tester szerint a momentum nem fordít előjelet, és az ICE-nél a két tag részben kioltja egymást.

## Javasolt teendők (prioritás szerint)

1. A `data/top_modellek.json` frissítése a 2026-10-13-i jarmuipar.hu cikkből. Ez az egyetlen determinisztikus WARN, és a nyilvános oldalon elavulás-figyelmeztetést okoz.
2. Döntés a tényezők „folytatódik a trend” feltevéséről: zsugorítás a 0 felé a szentimentnél, a kamatnál és az üzemanyagnál.
3. A töltőinfra-kártya walk-forward újraértékelése (naiv vagy rövidebb ablak), a CLAUDE.md „0,82×” állításának frissítése.
4. Új EAFO-export (2026 Q3).
5. A Következtetés-szövegek: piacsúlyozott előjel, ne rangsoroljanak küszöbközeli értékeket.
