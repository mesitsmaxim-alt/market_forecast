# Validációs audit – 2026-10-09

**Végső ítélet: FAIL**

**Publikálási javaslat:** A dashboard frissítését ne publikáld, amíg két dolog nincs javítva. Az egyik a backtest-riport nem szignifikáns eredményre tett „érdemben jobb a véletlennél” állítása. A másik az Előrejelzés-fül két kártyacsoportja (szentiment, alapkamat): ezek mintán kívül rosszabbak a naiv „marad az utolsó érték” becslésnél. A modell számítása helyes, és a fő hajtásirányok robusztusak. A gond a predikciók közlésével van, nem a motorral.

## Determinisztikus ellenőrzés

`validate_forecast.py --stage all`: **WARN** (pre: WARN, post: PASS), részletek: [validacio_riport.md](validacio_riport.md).
Mind a 22 CRITICAL invariáns OK. Az egyetlen nem-OK ellenőrzés a `backtest.fresh`, ez hamis riasztás (lásd lent).

## Ítéletek

| terület | agent | verdikt | területi ítélet |
|---|---|---|---|
| A. Modell | forecast-invariant-checker | WARN | **WARN** |
| | forecast-calibration-auditor | WARN | |
| B. Predikciók | forecast-stats-reviewer | FAIL | **FAIL** |
| | forecast-prediction-tracker | FAIL | |
| C. Feltételezések | forecast-source-verifier | WARN | **WARN** |
| | forecast-assumption-stress-tester | WARN | |
| | forecast-plausibility-reviewer | WARN | |

---

## A. Modell – helyesen számol-e?

**Igen.** A 8 tényező `alap` értéke és sávja független újraszámolással egyezik (a legnagyobb eltérés 0,084, a tűrés 0,15). A 24 szintetikus egységteszt mind sikeres (`compute_segments`, momentum-sapka, `classify` küszöbök, `linreg_forecast`, `forecast_card`). A 22 CRITICAL invariáns OK. A gyengeségek módszertaniak, nem számítási hibák.

| tényező | alap (config) | alap (független) | sáv (config) | sáv (független) | egyezik |
|---|---|---|---|---|---|
| oil_price | 12,9 | 12,892 | ±12,3 | ±12,311 | igen |
| financing_cost | −1,0 | −1,0 | ±3,6 | ±3,619 | igen |
| charging_infra | 5,7 | 5,668 | ±11,0 | ±11,049 | igen |
| consumer_sentiment | 11,6 | 11,633 | ±10,5 | ±10,475 | igen |
| purchasing_power | 1,7 | 1,7 | ±4,9 | ±4,863 | igen |
| battery_cost | −8,0 | −8,0 | ±6 | ±6 | igen |
| ev_tariffs | −1,0 | −1,0 | ±10 | ±10 | igen |
| co2_regulation | 14,5 | 14,584 (dátumeltolódás) | ±4 | ±4 | igen |

### WARN
- **A tényezők skálája nem egységes.** Az `engine.py:199` minden deltát `/100`-zal normalizál, de a tényezők mértékegysége eltér: pp (kamat), balance-pont (szentiment), % (olaj, CO2). Ezért 1 pp kamatváltozás ugyanannyi súlyt kap, mint 1% üzemanyagár-változás. Csak a kézi érzékenységek kompenzálhatnák ezt, de ez nincs dokumentálva. *Forrás: calibration-auditor.*
  Javaslat: normalizálás a tényező saját sáv-szórásával (z-skála), vagy a skála-feltevés dokumentálása a `segments.json`-ban.
- **A backtest másképp méri a tényezőket, mint az éles kalibráció.** A `backtest.py:99-103` évvégi kamatkülönbséget, éves szentiment-átlagot és HICP éves átlagot használ. Az éles kalibráció ehelyett 12 havi Δ-t, 3 havi átlagot és heti kútár YoY-t számol. A backtest ezért csak közelítőleg validálja az éles modellt. *Forrás: calibration-auditor.*
  Javaslat: a backtest használja az éles definíciókat, vagy a riport mondja ki az eltérést.

### INFO
- Az `alapkamat_forecast` a döntések indexén fut, nem időn: a 17 hónapos szünet egyetlen lépésnek számít. *Forrás: calibration-auditor.*
- A `co2_regulation` szint-jellegű (szükséges éves csökkentés), nem változás. Ezért állandó negatív tagot ad az ICE-nek. Ezt a módszertani blokkban érdemes jelezni. *Forrás: calibration-auditor.*
- A `backtest.py` docstringje 3 tényezőt említ, a kód 4-et használ. *Forrás: calibration-auditor.*
- A mai build (`generated` 2026-10-09) tartalma 8 napos: ma fetcher nem futott, az üzemanyagár a 10-01-i (benzin 636, dízel 709 Ft). A `dashboard.fresh` ellenőrzés ezt nem látja. *Forrás: invariant-checker.*

---

## B. Predikciók – bejön-e, amit mond?

**Nagyrészt nem.** Mintán kívüli walk-forward teszten a dashboard Előrejelzés-fülének lineáris trendvetítései többnyire rosszabbak a random walknál. A ±1σ sávok 0–42%-ban fedik le a tényleges értéket a névleges ~68% helyett. A backtest egyik eredménye sem szignifikáns (p = 0,40–0,51). Kivétel az állomány-részesedés pontvetítése: az jobb a naivnál, de a sávja ott is félrevezető.

| vetítés | n | MAE | MAE random walk | lefedettség | irány |
|---|---|---|---|---|---|
| alapkamat (w8, 1 lépés) | 149 | 0,812 | 0,512 | 23% | 64% |
| EUR/HUF (w24, 6 hó) | 207 | 11,26 | 7,79 | 42% | 55% |
| töltőinfra (w8, 4 negyedév) | 15 | 546 | 407 | 13% | 93% |
| forgalomba (w8, 4 negyedév) | 7 ⚠ kis n | 6104 | 5365 | 25% | 43% |
| szentiment – vásárlási szándék (w36, 6 hó) | 363 | 8,86 | 4,65 | 34% | 45% |
| fogyasztói bizalom (w36, 6 hó) | 363 | 10,67 | 5,28 | 33% | 42% |
| reálkereset (w10, 2 év) | 24 | 5,47 | 4,57 | 33% | 38% |
| reáljövedelem (w10, 2 év) | 24 | 4,07 | 3,19 | 40% | 54% |
| állomány-részesedés benzin (w6, 2 év) | 17 | 0,764 | 1,869 | 9% | 100% |
| állomány-részesedés hibrid | 17 | 0,385 | 0,550 | 0% | 94% |
| állomány-részesedés elektromos | 17 | 0,119 | 0,141 | 9% | 59% |

*A vágások átfedők, ezért a független minta kisebb. Az alapkamat és a szentiment számait az orchestrator újraszámolta: pontosan egyeznek.*

### CRITICAL
1. **A backtest-riport nem szignifikáns eredményre állítja, hogy „érdemben jobb a véletlennél”.** A `backtest.py:207` fix küszöbbel dolgozik (`hit >= 0.6`), és így a 14/23-as (61%) BEV-találatra kiírja ezt a mondatot. A binomiális p = 0,405 (az orchestrator ellenőrizte), a Wilson 95% CI 41–81%. A marginálisokból vett véletlen alapérték 63,5%, ehhez képest a 61% nem jobb. Ez ellentmond a CLAUDE.md elvének („report results honestly”), és a riport a publikus repóban van. *Forrás: stats-reviewer.*
   Javaslat: az „Értelmezés” a p-értékből generálódjon. p ≥ 0,05 esetén a szöveg: „nem különböztethető meg a véletlentől”. A korrelációknál is szerepeljen p-érték és CI (BEV r = 0,15, p = 0,50; hibrid r = 0,17, p = 0,45).
2. **A szentiment-vetítések (`mp_forecast`, `cc_forecast`) kétszer rosszabbak a naiv becslésnél, és az irányt a véletlennél rosszabbul találják el.** MAE 1,91× és 2,02× a random walkhoz képest, irány 45% és 42%, lefedettség 33–34%. A `cc_forecast` ráadásul 7 ponttal az utolsó mért érték alól indul. *Forrás: prediction-tracker, stats-reviewer.*
   Javaslat: a vetítés levétele a két kártyáról, helyette mozgóátlag vagy „nincs megbízható irány” jelzés.
3. **Az alapkamat-vetítés rosszabb a random walknál, a sávja pedig nulla szélességű.** MAE 1,59×, lefedettség 23%, `lower = upper = 5,25`, mert a 8 pontos ablak tökéletesen lineáris. Ez hamis bizonyosságot sugall egy jegybanki döntésről. *Forrás: prediction-tracker, stats-reviewer.*
   Javaslat: az alap legyen a „marad”, vagy a kártya mutasson csak irányt, minimum ±0,25 pp sávval.

### WARN
- **A ±1σ sávok szisztematikusan túl szűkek.** A reziduál-szórás az illesztés hibáját méri, nem az előrejelzési hibát, és a horizonttal sem szélesedik. Érinti az állomány-részesedést (lefedettség 0–12%), a töltőinfrát (13%) és az EUR/HUF-ot (42%). *Forrás: prediction-tracker, stats-reviewer.*
  Javaslat: a `forecast.py` sávja a walk-forward előrejelzési hibákból, vagy legalább n−2 osztású, horizonttal szélesedő predikciós intervallumból jöjjön.
- **A töltőinfra-vetítés ellentmond a kalibrációnak.** 4 negyedév alatt +18%-ot vetít, a kalibráció YoY-ja +5,7%. Az első pont +368 db, miközben az utolsó negyedéves változás +41 volt. A meredekséget egy +686-os ugrás húzza. *Forrás: stats-reviewer.*
- **A forgalomba helyezési vetítés nem kezeli a szezonalitást.** A Q3 mind a 4 évben ~4%-kal a Q2 alatt van, a vetítés mégis a Q2 szintjéről indul. A kis n miatt (7) erős következtetés nem vonható le. *Forrás: stats-reviewer, prediction-tracker.*
- **EUR/HUF és reálkereset/reáljövedelem:** rosszabbak a random walknál (1,2–1,44×). A bérsor meredeksége nem szignifikáns (|t| < 2), a dashboard mégis irányt mutat. *Forrás: prediction-tracker, stats-reviewer.*
  Javaslat: ha |t| < 2, a kártya írja ki: „nincs szignifikáns trend”.
- **A backtest célváltozója erősen autokorrelált (0,98).** A hatékony n jóval 23 alatt van, ezért a p-értékek még optimisták is. A 2003–09-es években a találat 2/7. *Forrás: stats-reviewer.*
  Javaslat: differenciált vagy detrendelt cél, naiv alapmodellel összevetve.
- **A dashboard backtest-blokkja:** a „weak” jelzés csak `hit_rate <= 0.55` esetén kapcsol be, ezért a BEV 61%-a figyelmeztetés nélkül jelenik meg. *Forrás: stats-reviewer.*

### INFO
- **A modell saját korábbi állításai (`snapshots.jsonl`):** 5 független nap van. A BEV > PHEV > HEV > ICE sorrend mind az 5 napon stabil. A nagyságok és a márka-sorrend a módszertani javítások miatt mozogtak, nem piaci adat miatt. Ex-post értékelés még nem lehetséges: az első összevetés a 2026 Q3-as KSH-közlés után (nov. közepe–vége) lehetséges, az éves hajtásirány a 2026-os Eurostat-adat után (2027 H1). *Forrás: prediction-tracker.*

---

## C. Feltételezések – igazak és robusztusak-e?

**A bemenetek igazak, a fő hajtásirányok robusztusak, a finomabb állítások nem.** A kézi források (akkuár, EV-vámok, CO2) elsődleges forrással egyeznek. Az „ICE visszaesik, BEV a legerősebb” következtetés egyetlen egyedi ±0,5-ös együttható-eltolástól sem fordul meg, és 500 véletlen perturbáció (±0,15, seed 42) egyikében sem. Momentum nélkül is ugyanaz az irány jön ki. A márka-rangsor, a HEV–PHEV sorrend és több kártya címkéje viszont véletlenszerű. A „trend folytatódik” alapfeltevés két tényezőnél nem tartható.

| összesítő | alap | előjel-stabilitás | címke-stabilitás |
|---|---|---|---|
| BEV | +0,331 | 100% | 100% |
| PHEV | +0,181 | 100% | 97,8% |
| HEV | +0,168 | 100% | 86,6% |
| ICE | −0,130 | 100% | 90,4% |
| tömeggyártó | +0,151 | 100% | 51,2% (0,001-re a küszöbtől) |
| prémium | +0,162 | 100% | 75,6% |
| kínai belépő | +0,165 | 100% | 82,0% |
| budget | +0,073 | 100% | 92,2% |

Rangsor-stabilitás: a hajtás-rangsor 69,6%, és csak a HEV–PHEV pár instabil. A márka-rangsor 32,4%, a legjobb szegmens 49,2%.

### WARN
- **A „trend folytatódik” feltevés nem tartható a `consumer_sentiment` és az `oil_price` tényezőnél.** Történetileg a következő 12 havi változást a „nulla változás” becslés jobban eltalálta, mint a mostani 12 havi Δ: a szentimentnél a MAE 1,60×, az olajárnál 1,31×, az irány 47–50% (véletlen szint). A `financing_cost` is gyengébb (1,34×). A `charging_infra` és a `purchasing_power` esetében viszont a feltevés védhető. *Forrás: prediction-tracker.*
  Javaslat: a kalibrációban az `alap` a 0 felé legyen húzva (pl. 50% perzisztencia) ezeknél a tényezőknél.
- **Az `oil_price` alapja egyetlen heti kútár-YoY (+12,9%), miközben a HICP üzemanyag-index ugyanerre az időszakra kb. +1%-ot mutat** (2026-06/07/08: +2,3 / −0,1 / +1,3). Ez a legérzékenyebb tényezők egyike: nélküle az ICE „Stagnálás” lenne. Az ICE „Visszaesés” címkéje az olaj- és a CO2-feltevésen múlik, a kettő együttes kiejtésével az előjel is megfordul. *Forrás: calibration-auditor, stress-tester.*
  Javaslat: a következő HICP-hónap után ellenőrizni, vagy az alapot a heti és a havi forrás keverékéből számolni.
- **A márka-rangsor véletlenszerű, mégis a dashboard rangsoroló mondatot generál.** A kínai belépő, a prémium és a tömeggyártó 1,4 ponton belül van. A teljes rangsor a perturbációk 32%-ában marad meg. *Forrás: stress-tester.*
  Javaslat: 3 pont alatti különbségnél a szöveg legyen „gyakorlatilag azonos”.
- **Több címke küszöbön ül.** A tömeggyártó 0,151-gyel áll a 0,15-ös küszöbön, az idősebb használt 0,056-tal a 0,05-ösön, és a piacsúlyozott értékek 0,043–0,057 között vannak. *Forrás: stress-tester.*
  Javaslat: hiszterézis, vagy „határeset” jelölés.
- **A momentum 7 szegmensben a pontszám felénél nagyobb** (budget HEV / idősebb: 84%). Ez ellentmond a „kiegészítő jelzés” elvnek. *Forrás: plausibility-reviewer.*
- **A fogyasztói szándék tényező túlsúlyos.** Új évjáratnál a pontszám 41%-át adja, miközben a mutató szintje negatív (−16), és a tényező alapfeltevése a legkevésbé tartható (lásd fent). *Forrás: plausibility-reviewer, stress-tester.* Kapcsolódik a fenti perzisztencia-találathoz.
- **A budget ICE a modellben a legrosszabb, a KSH-adat ezt nem támasztja alá.** Az utolsó 4 negyedévben a Dacia +23,7%, a Fiat +12,4%, a teljes piac +15,2%. *Forrás: plausibility-reviewer.*
  Javaslat: a budget × `co2_regulation` és a budget × `oil_price` érzékenység felülvizsgálata.

### INFO
- Az egyszerű és a piacsúlyozott átlag előjele eltér a budget (+0,073 vs −0,036) és az idősebb használt (+0,056 vs −0,072) csoportnál. Ez dokumentált korlát, de a „Növekedés” főcím ott félrevezető. *Forrás: plausibility-reviewer, stress-tester.*
- A kínai belépő kategóriának nincs regisztrációs momentuma, mert a BYD, MG és Nio nincs a KSH-listán. *Forrás: plausibility-reviewer, stress-tester.*
- Kézi források:
  - `akkuar.json`: BNEF 108 $/kWh, −8%, a következő felmérés 2026 decemberében;
  - `ev_vamok.json`: a VW Anhui árkötelezettség az egyetlen elfogadott;
  - `co2_szabalyozas.json`: a −90%-os javaslat helyesen nincs a számításban, a parlamenti szavazás 2026 novemberében várható.

  *Forrás: source-verifier.*
- Új EAFO-export ajánlott, mert a Q3 szeptember 30-án lezárult. A `top_modellek.json` frissítéséhez a jarmuipar.hu szeptemberi Top cikkét kell megnézni. *Forrás: source-verifier.*
- A kézi tényezők fix sávja önkényes: az `ev_tariffs` sávja az alapérték 10×-e, a `co2_regulation` sávja 0,28×-a. *Forrás: stats-reviewer.*

---

## Lejjebb sorolt találatok (hamis riasztás vagy dokumentált korlát)

- **`backtest.fresh` (WARN → INFO).** A backtest 10-01-i, de a bemenő éves adatai (KSH 2003–2025) azóta nem változtak. Ma csak a dashboard-build futott, a pipeline nem. A `validate_forecast.py:225` szigorú `== today` feltétele túl szigorú egy havi pipeline-hoz. Javaslat: `(today − generated).days <= 35`. *Forrás: invariant-checker, source-verifier, calibration-auditor.*
- **A momentum az idősebb használt szegmensekre is kiterjed (INFO marad).** Dokumentált egyszerűsítés.
- **A backtest szűk, 4 tényezős (INFO marad).** Dokumentált (CLAUDE.md „Backtesting is intentionally narrow”). Ami túlmegy a dokumentált korláton, az a nem szignifikáns eredményre tett túlzó állítás: ez a B/CRITICAL 1.

## Javasolt teendők, prioritás szerint

1. `backtest.py`: p-érték alapú „Értelmezés”, és ugyanez a logika a dashboard backtest-blokkjában is. *(CRITICAL)*
2. Előrejelzés-fül: a szentiment-vetítés levétele, az alapkamat-kártya átalakítása irányjelzéssé. *(CRITICAL)*
3. `forecast.py`: walk-forward-hibából kalibrált, horizonttal szélesedő sáv, és „nincs szignifikáns trend” jelzés, ha |t| < 2.
4. Kalibráció: az `alap` 0 felé húzása a `consumer_sentiment`, az `oil_price` és a `financing_cost` tényezőnél, és egységes tényező-skála.
5. Dashboard-szöveg: márka-rangsor és küszöbközeli címkék jelölése.
6. Karbantartás: új EAFO-export, jarmuipar.hu Top lista, `backtest.fresh` küszöb, `backtest.py` docstring. Publikálás előtt friss pipeline-futás.
