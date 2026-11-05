# Validációs audit – 2026-10-09 (ismételt, a délelőtti javítások után)

**Végső ítélet: WARN**

**Publikálási javaslat:** A modell helyesen számol, a fő hajtásirányok robusztusak, a délelőtti FAIL két oka (backtest-szöveg, szentiment/alapkamat kártya) javítva és ellenőrizve. Publikálás előtt viszont javasolt az Előrejelzés fül egyetlen mondatát ([template.html:592](../dashboard/template.html)) javítani vagy a 4 érintett kártyát naivra váltani, mert a publikus oldal jelenleg valótlant állít róluk.

Ez az audit a délelőtti, FAIL ítéletű `validacio_audit_2026-10-09.md` utáni ismételt futás; az a fájl változatlanul megmaradt.

## Determinisztikus ellenőrzés

`python3 validate_forecast.py --stage all` → **PASS** (pre 15/15, post 18/18; nincs bukott és nincs WARN ellenőrzés). Részletek: [`reports/validacio_riport.md`](validacio_riport.md). A `dashboard/dashboard_data.json` mai (2026-10-09) build.

## Ítéletek

| Terület | Agent | Agent verdikt | Területi ítélet |
|---|---|---|---|
| A. Modell | forecast-invariant-checker | PASS | **PASS** |
| | forecast-calibration-auditor | PASS | |
| B. Predikciók | forecast-stats-reviewer | FAIL | **WARN** |
| | forecast-prediction-tracker | WARN | |
| C. Feltételezések | forecast-source-verifier | WARN | **WARN** |
| | forecast-assumption-stress-tester | WARN | |
| | forecast-plausibility-reviewer | WARN | |

A B területen a stats-reviewer FAIL-jét WARN-ra soroltam lejjebb (indoklás a B szakaszban és a lejjebb sorolt találatoknál).

---

## A. Modell — helyesen számol-e?

**Igen.** A script újrafuttatva PASS, és a calibration-auditor független kóddal (a `calibrate_factors.py` importálása nélkül) mind a 8 tényező alap értékét és sávját újraszámolta: a legnagyobb eltérés 0,10, tolerancián belül. A 24 szintetikus egységteszt (`classify`, `compute_segments` tényezőnként, momentum-sapka, `linreg_forecast`, `forecast_card`, `naive_forecast_card`) mind sikeres.

| tényező | alap (config) | alap (független) | sáv (config) | sáv (független) |
|---|---|---|---|---|
| oil_price | +12,9 | +12,89 | ±12,3 | ±12,31 |
| financing_cost | −1,0 | −1,00 | ±3,6 | ±3,62 |
| charging_infra | +5,7 | +5,67 | ±11,0 | ±11,05 |
| consumer_sentiment | +11,6 | +11,63 | ±10,5 | ±10,48 |
| purchasing_power | +1,7 | +1,70 | ±4,9 | ±4,86 |
| battery_cost | −8,0 | −8,0 | ±6 (fix) | ±6 |
| ev_tariffs | −1,0 | −1,0 | ±10 (fix) | ±10 |
| co2_regulation | +14,5 | +14,58* | ±4 (fix) | ±4 |

\* Időbeli sodródás: a `years_left` a futás napjától függ, a config 10-01-i. Nem hiba.

### WARN
- **Egységes `/100` skálázás eltérő mértékegységekre** (`engine.py:196`) — forrás: calibration-auditor. Bizonyíték: a %-ban mért oil_price alap-hozzájárulása +0,116, a pp-ben mért financing_cost-é −0,005; az ev_tariffs fix ±10 pp sávja a pesszimista/optimista ágon dominál, miközben az alapon elhanyagolható. Teendő: dokumentálni, hogy a skálák nem egységesek; mérlegelni az ev_tariffs sávjának szűkítését vagy az érzékenységek átskálázását.

### INFO
- `naive_forecast_card` szórása `E[x²]−E[x]²` képlettel, ami lebegőpontos hibából elvileg kicsit negatív lehet → `math.sqrt` ValueError (`forecast.py:80`). 20 000 véletlen konstans soron nem fordult elő. Teendő: `max(0, …)` védelem. — calibration-auditor
- `purchasing_power`: az alap a reáljövedelemből, a sáv a reálkereset változásaiból jön (`calibrate_factors.py:135`); a note kimondja. — calibration-auditor
- `battery_cost`: a BNEF közölt −8,0%-a eltér a fájl saját history-jából számolható −6,1%-tól; a kalibráció szándékosan a közölt értéket használja. — calibration-auditor
- A backtest proxyjai (év végi kamat, éves átlagos szentiment, HICP) eltérnek az élő kalibrációéitól; a backtest a modell hajtás-szintű, 4 tényezős szűkített változatát validálja. Dokumentált korlát. — calibration-auditor

---

## B. Predikciók — bejön-e, amit mond?

**Részben.** A délelőtti javítások beváltak: a backtest-szöveg most p-értékekre épül és őszinte (p-k függetlenül újraszámolva egyeznek), az alapkamat és a két szentiment-kártya naiv változata mintán kívül 1,6–2,0×-szer jobb a korábbi lineárisnál, a sávlefedettség 67–74% (névleges ~68%). Négy lineáris kártya viszont továbbra is rosszabb a „nem változik” becslésnél, és a lineáris kártyák sávjai jellemzően túl szűkek.

| vetítés | kártya | n (vágás) | MAE / naiv MAE | lefedettség |
|---|---|---|---|---|
| alapkamat | naiv | 153 | 1,00× (régi lineáris: 1,59×) | 67% |
| vásárlási szándék | naiv | 390 | 1,00× (régi: 1,91×) | 74% |
| fogyasztói bizalom | naiv | 390 | 1,00× (régi: 2,02×) | 74% |
| EUR/HUF | lineáris | 207 | 1,31–1,44× | 36–42% |
| töltőinfra | lineáris | 11–15 | 1,00–1,34× | 9–13% |
| reálkereset | lineáris | 22–24 | 1,20–1,34× | 23–33% |
| reáljövedelem | lineáris | 22–24 | 1,27–1,43× | 40–41% |
| forgalomba | lineáris | 3–7 (kis n) | 1,14× | 0–25% |
| állomány-részesedés (benzin/dízel/hibrid/BEV) | lineáris | 11–17 | 0,41–0,93× (pont jó) | 0–18% |
| állomány-részesedés (egyéb) | lineáris | 17 | 2,04× | 12% |

A két agent eltérő tartományai a vágási módszer különbségéből adódnak (expanding vs. átfedő ablakok); mindkettő ugyanazt az irányt mutatja.

### WARN
- **Az Előrejelzés fül szövege nem igaz 4 kártyára** — forrás: stats-reviewer (CRITICAL-ként jelezte), prediction-tracker. Bizonyíték: [`template.html:592`](../dashboard/template.html) általános szabályként állítja: „Ahol a trend a múltban rosszabbul jelzett előre, mint a »nem változik« feltevés, ott a kártya csak a mostani szintet … mutatja.” A `build_dashboard.py:451` (EUR/HUF), `:465` (töltőinfra), `:512–513` (reálbér, reáljövedelem) viszont lineáris `forecast_card`-ot használ, és ezek mintán kívül 1,2–1,44×-esen rosszabbak a naivnál. A bérkártya 4,8%-os utolsó értékről 2,1 → 1,5%-ra „vetít”, nem szignifikáns meredekséggel (t = −1,64, n=10). Teendő (publikálás előtt javasolt): vagy ezt a 4 kártyát `naive_forecast_card`-ra váltani (EUR/HUF band_window ≈ 120 hó, bérsorok ≈ 10 év), vagy a mondatot a ténylegesen átállított kártyákra szűkíteni.
- **Túl szűk sávok a lineáris kártyákon** — forrás: stats-reviewer, prediction-tracker. Bizonyíték: az állomány-részesedés sávja ±0,06–0,14 pp, walk-forward lefedettség 0–18% (a tényleges 2 éves hiba a félszélesség 5–8-szorosa); töltőinfra 9–13%. A reziduál-szórás az illesztés zaját méri, nem az előrejelzési hibát. Teendő: horizonttal szélesedő, mintán kívüli (h-lépéses) hibából képzett sáv, ahogy a naiv kártyáknál.
- **Töltőinfra-vetítés túl meredek** — forrás: stats-reviewer, prediction-tracker. Bizonyíték: slope +207 db/negyedév vs. az utolsó 5 negyedév ~124-es átlaga; a 4 negyedéves vetítés +18%, miközben a kalibrált `charging_infra` alap +5,7%. Teendő: robusztus/rövidebb meredekség vagy naiv kártya.
- **„Folytatódik a trend” tényező-feltevés nem tartható 3 tényezőnél** — forrás: prediction-tracker. Bizonyíték: a mostani 12 havi változás perzisztenciája a következő 12 hónapra rosszabb a nullánál: consumer_sentiment 1,60× (n=371, irány 47%), financing_cost 1,34× (n=399), oil_price 1,31× (n=278, irány 51%). A charging_infra és a purchasing_power esetén a feltevés védhető (kis n). Teendő: az alap értéket a 0 felé húzni (pl. 50%-os perzisztencia: szentimentnél MAE 14,4 → 11,2). Ez a modell központi feltevését érinti, ezért külön döntést igényel.
- **Állomány-részesedés „egyéb” kártya 2,04× rosszabb a naivnál** — forrás: prediction-tracker. Teendő: elhagyni vagy naivra cserélni.

### INFO
- Forgalomba-kártya: negyedéves szezonalitás nincs kezelve (Q3 mind a 4 évben alacsonyabb a Q2-nél), de n=3–7, nem értékelhető. Teendő: szezonális naiv összevetés, ha lesz ≥8 pont. — stats-reviewer, prediction-tracker
- Backtest: a célváltozó lag-1 autokorrelációja 0,98, az effektív n jóval kisebb 23-nál. Mivel a következtetés már „nem szignifikáns”, a hiba iránya konzervatív. Teendő: az Értelmezésben megemlíteni az effektív n-t. — stats-reviewer
- Alapkamat: a kamatlépések iránya 90%-ban tartós (139/155); az „utolsó lépés ismétlődik” becslés MAE-je 0,305 vs. naiv 0,570. A naiv kártya így is védhető, a sáv alsó széle lefedi a valószínű 5,25%-ot. — prediction-tracker
- A modell saját korábbi állításai (`snapshots.jsonl`, 5 független nap) még nem értékelhetők ex post; első lehetőség a 2026 Q3-as KSH-forgalomba-közlés után (nov. közepe–vége). — prediction-tracker

---

## C. Feltételezések — igazak és robusztusak-e?

**A bemenetek igazak, a fő következtetések robusztusak, a finomabb címkék nem.** Egyik kézi forrás sem bizonyult tévesnek, az adatminőségi szabályok (csonka EAFO-negyedév, befagyott Eurostat-sor) teljesülnek. A hajtásirányok (BEV↑, PHEV↑, HEV↑, ICE↓) 500 véletlen perturbációban 100%-ban, momentum nélkül is megmaradnak, és egyeznek a valós Eurostat-trendekkel (ICE új részesedés 70,2 → 35,0%, HEV 24,8 → 50,5%, BEV 2,4 → 8,5%, 2020–2025). A márka-rangsor és a küszöb-közeli címkék viszont törékenyek.

| következtetés | előjel-stabilitás | címke-stabilitás |
|---|---|---|
| BEV növekedés | 100% | 100% |
| PHEV növekedés | 100% | 97,8% |
| HEV növekedés | 100% | 86,6% |
| ICE visszaesés | 100% | 90,4% |
| hajtás-rangsor BEV>PHEV>HEV>ICE | — | 69,6% |
| márka-rangsor kínai>prémium>tömeggyártó>budget | — | 32,4% |
| tömeggyártó „Erős növekedés” | 100% | 51,2% |

(seed 42, 500 futás, minden együttható ±0,15)

### WARN
- **Márka-rangsor és küszöb-közeli címkék törékenyek** — forrás: assumption-stress-tester. Bizonyíték: a márka-rangsor csak 32,4%-ban stabil (kínai 0,1648 vs. prémium 0,1617, 0,3 pont különbség); a tömeggyártó 0,1510-zel 0,001-re ül az „Erős növekedés” küszöbe felett. Teendő: 3 pont alatti különbségnél „azonos sávban” megfogalmazás a `rankSentence`-ben; küszöb-közeli címkéknél jelzés.
- **Egyszerű átlag vs. piacsúlyozott ellentétes üzenet** — forrás: plausibility-reviewer, assumption-stress-tester. Bizonyíték: budget +0,0725 („Növekedés”) vs. piacsúlyozva −0,036; idősebb használt +0,056 vs. −0,072; tömeggyártó „Erős növekedés” vs. +0,043 (semleges sáv). A CLAUDE.md dokumentálja, a dashboard mindkettőt mutatja, de a fő címke az egyszerű átlagból jön, és két csoportnál az előjel is ellentétes. Teendő: a címkét/irányt a piacsúlyozott értékből adni, vagy a kettőt egyenrangúan mutatni.
- **Két tényező viszi a pontszámokat** — forrás: plausibility-reviewer, assumption-stress-tester. Bizonyíték: a consumer_sentiment 24/48 szegmensben a legnagyobb tétel (az új BEV +6,97 pontjából), elhagyva 11 aggregátum címkéje változik; a co2_regulation a 10 legérzékenyebb együtthatóból 8. A szentiment egyúttal a B szakaszban a leggyengébb perzisztencia-feltevés (1,60×). Teendő: a szentiment-érzékenységek felülvizsgálata, és a methodology blokkban jelezni, hogy ez a fő hajtóerő.
- **Momentum-dominancia 7 szegmensben** — forrás: plausibility-reviewer. Bizonyíték: pl. ICE kínai új −13,9 pontból −8,8 momentum; HEV budget új +17,8-ból +9,0. A hajtásirányok momentum nélkül sem fordulnak meg (stress-tester), de a márka-szintű „Erős növekedés” címkék a regisztrációs momentumtól függnek. Részben dokumentált. Teendő: a dashboardon jelezni.

### INFO
- `co2_szabalyozas.json` `proposals` (2035-re −90%) jogalkotási státusza nem volt megerősíthető; a source-verifier WARN-ként jelezte. Lejjebb sorolva: a modell a javaslatot helyesen nem számítja be, a hatályos 2035-ös 0 g/km mérföldkő helyes. Teendő: a 2025/0420(COD) aktát követni. — source-verifier
- `akkuar.json` 304 napos, de a BNEF éves (decemberi) felmérés; nincs újabb adat. Értékek egyeznek a BNEF-közleménnyel. — source-verifier
- `ev_vamok.json`: vámszintek és az első árkötelezettség (VW Anhui, 2026-02-10) egyeznek; újabb eseményt nem találtunk. Az alap forgatókönyvben a tényező hatása elhanyagolható, a pesszimista kínai-belépő „Visszaesés” viszont nagyrészt ebből jön. — source-verifier, stress-tester
- `top_modellek.json` 21 napos (küszöb 45), újabb jarmuipar.hu cikk még nincs; október második felében érdemes ránézni. — source-verifier
- `uzemanyagar_elo.json` 8 napos (2026-10-01); ha a dashboard novemberi pipeline előtt kerül publikálásra, érdemes a fetchert kézzel futtatni. — source-verifier
- A PHEV ≈ HEV pontszám (0,181 vs. 0,168) kissé túlbecsli a PHEV-et a valós trendhez képest; nem jelentős. — plausibility-reviewer
- Előjel-józanság, évjárat-súlyok ±20%, `changes` (üres, nincs mozgás 10-02 óta): rendben. — stress-tester, plausibility-reviewer

---

## Lejjebb sorolt találatok

| eredeti | új | találat | forrás | indoklás |
|---|---|---|---|---|
| CRITICAL | WARN | Az Előrejelzés fül szövege nem igaz az EUR/HUF, töltőinfra, reálbér, reáljövedelem kártyára | stats-reviewer | A megállapítás tényszerűen igaz (ellenőrizve: `template.html:592`, `build_dashboard.py:451/465/512–513`), de nem számítási hiba: minden szám helyes, és a kártyák felirata („becsült, az utolsó N év trendje alapján”) pontosan leírja, mit mutatnak. A rosszabb-a-naivnál arány 1,2–1,44×, a prediction-tracker saját FAIL-küszöbe (1,5×) alatt. Egyetlen mondat túláltalánosításáról van szó, ezért WARN — de publikálás előtt javítandó. |
| WARN | INFO | `co2_szabalyozas.json` javaslat-státusza nem ellenőrizhető | source-verifier | Nem bizonyított hiba; a modell a javaslatot helyesen nem számítja be, így bármi is a státusz, a jelenlegi bemenet helyes. |

## A délelőtti FAIL-audit tételei

| délelőtti találat | állapot |
|---|---|
| Backtest-riport „érdemben jobb a véletlennél” állítása | **javítva**, p-érték alapú szöveg, függetlenül ellenőrizve |
| Szentiment-kártyák rosszabbak a naivnál | **javítva**, naiv kártya, 1,00×, lefedettség 74% |
| Alapkamat-kártya rosszabb a naivnál | **javítva**, naiv kártya, lefedettség 67% |
| EUR/HUF, reálbér/jövedelem, szűk sávok, töltőinfra-meredekség, szezonalitás | **nyitott** (ld. B szakasz) |
