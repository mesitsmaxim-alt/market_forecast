# Autópiaci előrejelző és automatizált riportoló rendszer — prototípus

## Mit csinál

1. **Előrejelző modell** (`engine.py`): a piacot befolyásoló külső tényezők
   (olajár, akkumulátorár, töltőinfrastruktúra, EV-vámok, CO2-szabályozás)
   feltételezett elmozdulásait vetíti rá autópiaci szegmensekre
   (hajtástípus × márkakategória × évjárat-sáv), és minden szegmensre egy
   relatív **kitettségi pontszámot** számol: mennyire kedvez vagy árt neki az
   adott forgatókönyv.
2. **Riportgenerátor** (`generate_report.py`): a pontszámokból markdown
   riportot állít össze — összegzés tényezőnként, szegmensátlagok
   hajtástípus/márkakategória/évjárat szerint, top nyertes/vesztes
   szegmensek, teljes mátrix. Ez a rész futtatható **ütemezve** (naponta/
   hetente/havonta), így ez az "automatizált riportolási rendszer" magja.

A `config/factors.json` forgatókönyv-számait a `calibrate_factors.py` minden
futáskor valós adatból írja felül: 5 tényezőt automata forrásból, 3-at
(akkumulátorár, EV-vámok, CO2-szabályozás) kézi, forrásmegjelölt adatfájlból
(ld. lent, "Kézi forrású tényezők"). A `config/segments.json` érzékenységi
együtthatói továbbra is szakértői becslések — ez a "1. lépés" (tényező-alapú
előrejelzés) modellje.

A **"2. lépés" (szegmentált riportolás) már valós adaton fut**: a
`fetchers/fetch_jarmuallomany.py` letölti és feldolgozza a KSH STADAT
sza0025 táblát (személygépkocsi-állomány márkánként és hajtástípusonként,
2002-től), a `segment_report.py` pedig ebből tényleges piaci trendeket
(YoY, 5 éves CAGR, piaci részesedés, leggyorsabban növekvő/csökkenő
márkák) számol. Ez a rész nem becslés, hanem megfigyelt adat.

## Futtatás

Forgatókönyv-alapú előrejelzés (becsült tényezőkkel, 1. lépés):

```bash
cd market_forecast
python3 generate_report.py                  # alap forgatókönyv, 1 riport
python3 generate_report.py --scenario optimista
python3 generate_report.py --all-scenarios   # mindhárom forgatókönyv egy fájlban
```

Valós adatból számolt szegmens-trend (KSH-adat, 2. lépés):

```bash
cd market_forecast
python3 fetchers/fetch_jarmuallomany.py      # letölti + feldolgozza a KSH sza0025-öt -> data/jarmuallomany.json
python3 segment_report.py                    # trend-riport a friss adatból

python3 fetchers/fetch_uzemanyag_elo.py      # letölti az ÉLŐ, mindig aktuális üzemanyagárat -> data/uzemanyagar_elo.json
python3 fetchers/fetch_uzemanyagar.py        # letölti a KSH régiós üzemanyagár-táblát (kiegészítő, történeti) -> data/uzemanyagar.json
python3 fuel_report.py                       # üzemanyagár-trend riport (élő ár + HU vs. régió)

python3 fetchers/fetch_makro.py              # letölti az MNB alapkamat- és EUR/HUF-idősort -> data/makro.json
python3 makro_report.py                      # makró-trend riport (alapkamat, árfolyam)

python3 import_eafo_charging.py              # feldolgozza a kézzel exportált EAFO CSV-ket -> data/toltoinfra.json
python3 toltoinfra_report.py                 # töltőinfrastruktúra-trend riport

python3 fetchers/fetch_forgalomba.py         # letölti a KSH sza0070 negyedéves forgalomba helyezési adatot -> data/forgalomba.json
python3 forgalomba_report.py                 # gyors, előretekintő forgalomba helyezési trend riport

python3 fetchers/fetch_szentiment.py         # letölti az Eurostat fogyasztói szentiment-adatot -> data/szentiment.json
python3 szentiment_report.py                 # szentiment-trend riport (vásárlási szándék, fogyasztói bizalom)

python3 fetchers/fetch_realjovedelem.py      # letölti a KSH gdp0035 reáljövedelem/reálkereset-indexet -> data/realjovedelem.json
python3 realjovedelem_report.py              # reáljövedelem/vásárlóerő-trend riport

python3 fetchers/fetch_hirek.py              # 4 hazai RSS-forrásból piaci relevanciájú cikkeket gyűjt -> data/hirek.json
python3 hirek_report.py                      # piaci hírek riport, forrásonként csoportosítva
```

A riportok a `reports/` mappába kerülnek (`riport_...` a forgatókönyv-alapú,
`szegmens_riport_...` / `uzemanyag_riport_...` / `makro_riport_...` /
`toltoinfra_riport_...` / `forgalomba_riport_...` / `szentiment_riport_...` /
`realjovedelem_riport_...` / `hirek_riport_...` a valós adatos verziók).

A `data/top_modellek.json` (legkeresettebb modellek) kézi adatbevitellel
frissül — nincs hozzá fetcher/riport, ld. CLAUDE.md.

## Kalibráció valós adattal

```bash
python3 calibrate_factors.py   # frissíti config/factors.json oil_price és financing_cost blokkjait valós adatból
```

Ez a `config/factors.json`:
- `oil_price` blokkját a holtankoljak.hu **élő** adatából számolt, tényleges
  éves (YoY) árváltozásra állítja — ez **minden futáskor a ténylegesen
  aktuális árat** nézi, nem egy befagyott pillanatképet (jelenleg
  **+11,7%/év**, mert a benzin+gázolaj átlagár érdemben drágult az elmúlt
  12 hónapban), a pesszimista/optimista sávot pedig ±8 százalékponttal
  köré húzza;
- `financing_cost` blokkját (új tényező, ld. lent) az MNB alapkamat
  12 havi tényleges változására állítja (jelenleg **-1,0 pp/év**), ±1,5
  százalékpontos sávval;
- `charging_infra` blokkját az EAFO (kézzel importált) adatból számolt,
  magyarországi nyilvános AC+DC töltőpontszám tényleges éves (YoY)
  növekedésére állítja (jelenleg **-2,6%/év** — az AC-állomány egy friss,
  valószínűleg adatrevízióból eredő visszaesése húzza le az összesített
  számot annak ellenére, hogy a DC-gyorstöltők külön nézve +22,4%/év
  ütemben nőnek, ld. `toltoinfra_riport_...`), ±10 százalékpontos sávval;
- `consumer_sentiment` blokkját (új tényező, ld. lent) az Eurostat "tartós
  fogyasztási cikk vásárlási szándék" indikátorának tényleges 12 havi
  változására állítja (jelenleg **+13,5 pont/év**, erős javulás egy mély
  2025 őszi/2026 tavaszi völgy után), ±10 pontos sávval;
- `purchasing_power` blokkját (új tényező, ld. lent) a KSH reáljövedelem/
  reálkereset-index tényleges YoY változására állítja (jelenleg **+4,8%**,
  a 2025-ös reálkereset-adat, mert a szélesebb reáljövedelem-mutató még nem
  publikált erre az évre — a script automatikusan visszaesik a reálkeresetre,
  ha a reáljövedelem hiányzik), ±6 százalékpontos sávval.

**Új tényező: `consumer_sentiment`** — az egyetlen valóban ELŐRETEKINTŐ
indikátor a rendszerben (nem azt méri, mi történt, hanem mit terveznek az
emberek). Forrás: Eurostat `ei_bsco_m` (Business and Consumer Survey),
publikus REST API, autentikáció nélkül — `fetchers/fetch_szentiment.py` +
`szentiment_report.py`. Sensitivitása van minden hajtástípusnak (a drágább,
halasztható BEV/PHEV-vásárlás érzékenyebb a hangulatra, mint az ICE-csere),
minden márkakategóriának (a prémium/luxus vásárlás diszkrecionálisabb, mint
a budget) és évjárat-sávnak (az új autó vásárlása halasztható, az idősebb
használt lecserélése inkább kényszer, ezért kevésbé szentiment-függő).

**Új tényező: `purchasing_power`** — a reáljövedelem/vásárlóerő alakulása.
Forrás: KSH `gdp0035` (Reáljövedelem – reálbérindex), éves bontás —
`fetchers/fetch_realjovedelem.py` + `realjovedelem_report.py`. A növekvő
vásárlóerő a drágább/prémium/új szegmenseket segíti (BEV +0.3, prémium +0.4,
új autó +0.3), miközben az idősebb használt szegmens relatív vonzereje
**csökken** (-0.2) — ez az egyetlen tényező, ahol egy szegmens tudatosan
negatív érzékenységet kap, mert a jövedelem-hatás ("income effect") logikailag
elszívja a keresletet az olcsóbb szegmensektől a drágábbak felé, nem csak
egyenletesen növeli mindet.

**Új tényező: `financing_cost`** — a jegybanki alapkamat várható
elmozdulása. Sensitivitása van minden hajtástípusnak (a drágább, jellemzően
hitelből vett BEV/PHEV érzékenyebb, mint az ICE), minden márkakategóriának
(a budget/tömeggyártó vevők finanszírozás-függőbbek, mint a prémium/cash
vásárlók) és évjárat-sávnak (az új autó vásárlás inkább hitelből történik,
mint az idősebb használté). Forrás: `fetchers/fetch_makro.py` +
`makro_report.py` (MNB alapkamat-idősor és havi EUR/HUF árfolyam).

Emellett az `engine.py` minden hajtástípus-szegmenshez hozzáad egy
**"megfigyelt piaci momentum"** tagot, ami a `data/jarmuallomany.json`
(KSH sza0025) 3 éves CAGR-jából számol (pl. jelenleg BEV +42,5%/év,
hibrid/PHEV proxy +25,6%/év) — ez a riport `generate_report.py` kimenetében
a "Fő hajtóerő" listákban is megjelenik. Fontos: ez a tag **nem változik**
forgatókönyvenként (pesszimista/alap/optimista), mert egy tényleges,
megfigyelt trendet fejez ki, nem egy jövőbeli feltételezést — csak a
tényező-alapú (olajár, vám, stb.) rész forgatókönyv-függő.

A PHEV-hez nincs külön KSH-kategória (a statisztika csak "hibrid"-et közöl,
plug-in bontás nélkül), ezért a PHEV-momentum a hibrid CAGR-t használja
proxyként — ezt érdemes lesz pontosítani, ha lesz PHEV-specifikus forrás.

**Márkakategória-momentum** (`load_registration_momentum` az `engine.py`-ban)
— a KSH sza0070 negyedéves forgalomba helyezési adatából (nem az állományból,
hanem a friss új-regisztrációból, ami sokkal gyorsabban reagál a piaci
elmozdulásokra) számol egy YoY (azonos negyedév előző évhez képest) trendet
minden márkakategóriára, a `segments.json` `example_brands` listái alapján,
a márkák legutóbbi negyedéves volumenével súlyozva. Kisebb súllyal (0.1) és
nagyobb normalizálási sapkával (±40%) fut, mint az állomány-momentum, mert a
negyedéves adat zajosabb. A kínai eredetű (`kinai_belepo`) kategóriára nincs
adat, mert a BYD/MG/Nio még nem jelenik meg önálló sorként a KSH-táblában
(túl alacsony volumen) — ez a szegmens emiatt csak a forgatókönyv-tényezőkből
kapja a pontszámát, momentum nélkül.

## Minőségellenőrzés eredménye (2026-09-14)

Egy utólagos átvizsgálás során két problémát találtunk:

1. **Javított formázási hiba**: a `generate_report.py` tényező-táblázata
   korábban `:+.0f`-fel (egész számra) kerekített, ami félrevezető volt —
   pl. a finanszírozási költség pesszimista értéke ténylegesen +0,5pp volt,
   de "+0pp"-ként jelent meg. Mostantól 1 tizedesjegyre kerekít.

2. **Momentum-súly csökkentve (0.4 → 0.15)**: kiderült, hogy a "megfigyelt
   piaci momentum" tag a korábbi súllyal HEV/PHEV/BEV szegmenseknél **meghaladta
   a teljes pontszámot** (azaz a 6 forgatókönyv-tényező nettó *levont* a
   momentumból, nem az hajtotta a végeredményt) — a riport gyakorlatilag a
   múltbeli trendet ismételte meg, nem valódi forgatókönyv-érzékenységet
   mutatott. A csökkentett súllyal a momentum aránya kiegyensúlyozottabb lett
   (BEV: 92%, PHEV: 85%, HEV: 107%, ICE: 12% — korábban rendre 149%, 144%,
   158%, 42% volt), így a forgatókönyv-tényezők érdemben számítanak.

3. **Dokumentálva (nem hiba, csak névadási kétértelműség)**: a
   "pesszimista/alap/optimista" tengely a **zöld átállás (EV-adaptáció)
   szempontjából** pesszimista/optimista, nem általános gazdasági
   borúlátást/derűlátást jelent — pl. a pesszimista olajár-forgatókönyvben az
   olajár *esik* (rossz az EV-knek), ezért ilyenkor az ICE-szegmensek is
   nőhetnek. Ez most már explicit figyelmeztetésként szerepel minden
   `generate_report.py`-kimenet elején.

## Modell logikája

- Minden tényezőnek (`config/factors.json`) van egy **pesszimista/alap/
  optimista** forgatókönyv-értéke (várható %-os elmozdulás 12 hónapon belül).
  **Fontos:** ez a tengely a zöld átállás szempontjából pesszimista/optimista,
  nem általános gazdasági borúlátás/derűlátás (ld. "Minőségellenőrzés" fent).
- Minden szegmens-dimenziónak (`config/segments.json`: hajtástípus,
  márkakategória, évjárat-sáv) van egy **érzékenységi együtthatója**
  (-1..+1) minden tényezőre — ez fejezi ki, hogy az adott tényező
  elmozdulása mennyire és milyen irányban hat rá.
- A szegmens pontszáma = Σ(tényező delta × érzékenység) × évjárat-súly.
- A pontszám **relatív irányjelzés**, nem abszolút eladásszám-előrejelzés.

## Adatforrások (a teljes katalógus: `magyar_autopiac_adatforrasok.xlsx`)

A projekthez összeállított forráskatalógus alapján az alábbi ingyenes
forrásokat érdemes sorban bekötni:

| Tényező | Forrás | Státusz |
|---|---|---|
| Szegmens-súlyok (márka × hajtás × év) | KSH STADAT sza0025 | ✅ bekötve (`fetchers/fetch_jarmuallomany.py`) |
| Ár × évjárat × márka mikroadat | KSH × Használtautó.hu kísérleti statisztika | Terv |
| Friss forgalomba helyezés (márkánként, negyedéves) | KSH STADAT sza0070 | ✅ bekötve (`fetchers/fetch_forgalomba.py`, `forgalomba_report.py`), márkakategória-momentumként az `engine.py`-ban is |
| Olajár / üzemanyagár | **holtankoljak.hu (élő, napi frissülő)** | ✅ bekötve (`fetchers/fetch_uzemanyag_elo.py`) — ez hajtja az `oil_price` kalibrációt, **mindig a ténylegesen aktuális árat** használja (nem befagyott pillanatkép). A KSH régiós tábla (`fetchers/fetch_uzemanyagar.py`) megmaradt kiegészítő, történeti regionális (HU vs. szomszédos országok) kontextusnak a `fuel_report.py`-ban, de azt már nem a kalibráció használja. |
| Töltőinfrastruktúra | EAFO (AC/DC töltőpontszám, teljesítmény-kategória szerint) | ✅ bekötve, de **kézi import** (`import_eafo_charging.py`) — a MEKH cikkoldal és az EAFO dashboard is JS-alapú SPA, curl-lal nem elérhető, ezért a grafikonok "Download CSV" gombjával kézzel exportált fájlokat dolgozzuk fel. Frissítéshez: töltsd le újra a CSV-ket https://alternative-fuels-observatory.ec.europa.eu/transport-mode/road/hungary/infrastructure oldalról a `data/raw_eafo/` mappába, majd futtasd újra a scriptet. |
| EV-állomány (kiegészítés) | KSH STADAT sza0025 (hajtástípus-bontás, már benne van) | ✅ bekötve |
| Akkumulátorár | BloombergNEF éves Li-ion csomagár-felmérés | ✅ kézi forrás (`data/akkuar.json`), `battery_cost` tényező |
| EV-vámok | Európai Bizottság DG TRADE (kínai BEV kiegyenlítő vámok, árkötelezettség-vállalások) | ✅ kézi forrás (`data/ev_vamok.json`), `ev_tariffs` tényező |
| CO2-szabályozás | EU 2019/631 rendelet flotta-CO2 céljai + függő módosító javaslatok | ✅ kézi forrás (`data/co2_szabalyozas.json`), `co2_regulation` tényező |
| Makró — alapkamat, árfolyam | MNB (`alapkamat.xlsx`, `hu0301_arfolyam.xls`) | ✅ bekötve (`fetchers/fetch_makro.py`, `makro_report.py`), új `financing_cost` tényezőként az `engine.py`-ban is |
| Makró — infláció (CPI) | KSH | Terv |
| Reáljövedelem / vásárlóerő | KSH STADAT gdp0035 (Reáljövedelem – reálbérindex) | ✅ bekötve (`fetchers/fetch_realjovedelem.py`, `realjovedelem_report.py`), új `purchasing_power` tényezőként az `engine.py`-ban is |
| Szentiment / vásárlási szándék | Eurostat `ei_bsco_m` (EU Business & Consumer Survey) | ✅ bekötve (`fetchers/fetch_szentiment.py`, `szentiment_report.py`), új `consumer_sentiment` tényezőként az `engine.py`-ban is — publikus REST API, nincs auth, nincs scraping |
| Szentiment — kiegészítés (magyar nyelvű, kvalitatív) | GKI konjunktúraindex | Terv, alacsony prioritás (az Eurostat-adat már lefedi ugyanezt hivatalos, gépi úton elérhető formában) |

Minden fetcher script ugyanazt a mintát követi, mint a
`fetchers/fetch_jarmuallomany.py`: letölti a forrást (`curl`, mert a rendszer
Python `urllib`-je nem látja a macOS keychain tanúsítványait — ez ismert
python.org-telepítős probléma), feldolgozza, és strukturált JSON-t ír a
`data/` mappába. A `config/factors.json` értékei ezekből a JSON-okból
számolt tényleges %-os elmozdulások.

### Kézi forrású tényezők (akkumulátorár, EV-vámok, CO2-szabályozás)

Ehhez a 3 tényezőhöz nincs ingyenes, gépileg lekérdezhető forrás (a BNEF
csak éves sajtóközleményt ad ki, a vámok és CO2-célok jogszabályi események),
ezért — a `data/top_modellek.json` mintájára — kézzel karbantartott,
forrásmegjelölt JSON-fájlokból kalibrálódnak. Mindegyikben van `source_url`,
`updated` és `note` (frissítési útmutató). A kalibráció módja:

- **`battery_cost`** — a BNEF által közölt éves csomagár-változás (%), ±6 sáv.
  Frissítés: minden decemberben, az új BNEF-közleménykor.
- **`ev_tariffs`** — a ±12 hónapos ablakba eső hatályos események
  (`events[].impact_pp`) összege: a kínai BEV-import effektív átlagvámjának
  becsült változása (pp), ±10 sáv. Az eseményenkénti hatás durva becslés,
  az `impact_basis` mező indokolja. Frissítés: új DG TRADE döntésnél.
- **`co2_regulation`** — a következő hatályos flotta-CO2 mérföldkőig évente
  szükséges csökkentés (%/év, lineárisan), ±4 sáv. A `proposals` (pl. a 2035-ös
  −90%-os javaslat) nem számít bele, amíg el nem fogadják.

Ha egy fájl `updated` dátuma régebbi a küszöbnél (akkuár: 395 nap, vámok/CO2:
183 nap), a `calibrate_factors.py` figyelmeztetést ír a konzolra/naplóba és a
tényező `note`-jába. A dashboardon ezek "◐ kézi forrás" jelzést kapnak.
Bevezetéskor (2026-09-28) a CO2-tényező alap értéke 6-ról 14,4-re nőtt; a
szegmens-pontszámokban így sem lett domináns (átlagos részarány 14%, 48-ból 2
szegmensben a legnagyobb driver), ezért nem kapott külön skálázást.

## Automatizálás (ütemezés) — ✅ bekapcsolva

A teljes pipeline (adatletöltés → kalibráció → minden riport) egyben fut a
`run_pipeline.sh`-sal, és `launchd`-vel (macOS natív ütemezője) **havonta,
minden hónap 1-jén 10:00-kor** automatikusan lefut.

```bash
./run_pipeline.sh   # kézi futtatás bármikor
```

launchd-beállítás: `~/Library/LaunchAgents/com.maxim.marketforecast.pipeline.plist`.
Fontos: a `launchd` egy nagyon minimális `PATH`-t ad a job-nak (nincs benne a
python.org-os `python3`), ezért a plist explicit `EnvironmentVariables/PATH`
bejegyzést tartalmaz — enélkül a job csendben hibázna.

Hasznos parancsok:

```bash
launchctl list | grep marketforecast                                  # fut-e / státusz
launchctl kickstart -k gui/$(id -u)/com.maxim.marketforecast.pipeline # azonnali tesztfuttatás
launchctl unload ~/Library/LaunchAgents/com.maxim.marketforecast.pipeline.plist  # kikapcsolás
```

Logok: `logs/run_<időbélyeg>.log` (a pipeline saját logja, lépésenkénti
kimenettel), `logs/launchd.out.log` / `logs/launchd.err.log` (launchd-szintű
stdout/stderr, csak akkor van benne bármi, ha a script el sem indult).

**Fontos korlát:** a `toltoinfra_report.py` és a `charging_infra` kalibráció
mindig a `data/toltoinfra.json` **utoljára kézzel importált** állapotát
használja — az automata havi futás ezt nem frissíti, mert az EAFO-adatot
nem lehet programból letölteni. Ha friss töltőinfra-adatot szeretnél, időnként
kézzel újra kell futtatni az `import_eafo_charging.py`-t (ld. fentebb).

Ha a gépet gyakran kikapcsolod: a `launchd` a `StartCalendarInterval` job-ot
csak akkor indítja el, ha a gép épp be van kapcsolva a megadott időpontban —
kihagyott futtatást nem pótol automatikusan. Ha ez gond, a felhő-alapú
ütemezés (Claude Code `/schedule` skill) lenne az alternatíva, de ahhoz a
projektet előbb git repóba kellene tenni (a cloud agent nem éri el a helyi
fájlrendszert).

## Riport-kézbesítés

A pipeline utolsó lépéseként fut a `digest_report.py`, ami a
`dashboard/dashboard_data.json`-ból egy **egyoldalas, gyorsan átfutható
összefoglalót** ír a `reports/DIGEST.md`-be (mindig felülíródik — ez mindig
"a legfrissebb állapot" egy helyen, a 8 külön riportfájl böngészése
helyett), és **macOS értesítést** küld (`osascript display notification`)
a futás végén, a legfontosabb számokkal.

```bash
python3 digest_report.py   # kézzel is futtatható, ha csak a digest-et akarod frissíteni
```

Ez teljesen felügyelet nélkül is működik (kipróbáltuk `launchctl kickstart`-tal
triggerelve, nem csak kézi terminálból) — a `run_pipeline.sh` úgy van
megírva, hogy egy esetleges értesítési hiba (pl. nincs bejelentkezett
GUI-munkamenet) ne buktassa el a teljes futást.

**Amit ez NEM helyettesít:** ez egy helyi macOS Notification Center üzenet,
nem email/Slack — csak akkor látod, ha épp a gépnél vagy, amikor lefut (vagy
utólag megnyitod a Notification Centert). Ha távolról / máshonnan is
szeretnél értesítést kapni, egy SMTP-vel küldött e-mail vagy egy Slack
webhook lenne a következő lépés — mindkettőhöz külső hitelesítő adat
(jelszó/API-kulcs) kellene, amit még nem állítottunk be.

## Dashboard (Artifact)

A projekthez tartozik egy publikált, vizuális HTML dashboard (Claude
Artifact), ami a forgatókönyv-tényezőket, a szegmens-pontszámokat és a
valós adatforrásokat egy oldalon foglalja össze — lásd a lentebbi linket
(a felhasználónál van elmentve, `action: "list"`-tel is visszakereshető).

```bash
python3 dashboard/build_dashboard.py   # frissíti dashboard/dashboard.html-t a legfrissebb adatokból
```

Ez **a `run_pipeline.sh` utolsó lépéseként automatikusan lefut** minden
hónapban — az adatok mindig frissek a `dashboard/dashboard.html`-ben.

**Fontos korlát:** a tényleges publikálás (hogy a friss HTML tényleg
megjelenjen az élő linken) **csak egy aktív Claude Code munkamenetből**
lehetséges, mert az Artifact-publikálás a Claude Code eszközrendszerének
része, amit egy sima `launchd`/bash-job nem tud önmagában meghívni. Ezért
ez a lépés **félautomata**: az adat és a HTML mindig friss és publikálásra
kész, de a tényleges frissítéshez kérd meg Claude-ot ("frissítsd a
dashboardot") — ekkor egyetlen paranccsal (`Artifact` a meglévő URL-lel)
újrapublikálja.

Teljesen felügyelet nélküli, ütemezett publikálás technikailag
megvalósítható lenne (a `launchd` a `claude -p` non-interaktív CLI-t hívná
sima bash helyett), de ehhez Node.js + a Claude Code CLI telepítése és egy
**engedély-megkerülő mód** bekapcsolása kellene — ez utóbbi azt jelenti,
hogy egy felügyelet nélküli folyamat emberi jóváhagyás nélkül futtatna
parancsokat és publikálna egy élő linkre. Ez tudatos kockázatvállalás,
ezért nincs alapértelmezetten bekapcsolva.

## Backtesting

```bash
python3 backtest.py   # visszaméri a segments.json érzékenységi együtthatóit valós, történeti adaton
```

**Amit mér:** a `config/segments.json`-ban kézzel megadott érzékenységi
együtthatókat (pl. "BEV `financing_cost` sensitivity = -0.5") sosem mértük
vissza valósághoz — ezek szubjektív becslések voltak. A `backtest.py` ezt
teszi meg: 2003–2024 közötti minden évre kiszámolja a BEV/Hibrid vs. ICE
tényleges (KSH-adatból mért) piaci részesedés-elmozdulást, és összeveti a
modell 3 (a 8-ból ténylegesen visszamérhető) tényezőjéből számolt
előrejelzéssel. Eredmény (`reports/backtest_riport.md`):

- **Hit rate: 64%** (n=22 év) — jobb, mint a véletlen (50%), tehát az
  együtthatók **iránya** részben helyes megérzés volt.
- **Korreláció: +0,05** — gyenge, tehát az együtthatók **nagyságrendje**
  (relatív súlyuk egymáshoz képest) nincs jól kalibrálva.

**Fontos korlátok, amiket a riport is explicit módon leír:**
- Csak 4 a 8 tényezőből tesztelhető (finanszírozási költség, vásárlóerő,
  fogyasztói szándék, és 2026-10-01 óta az üzemanyagár az Eurostat HICP-
  üzemanyagindexéből, `fetchers/fetch_uzemanyag_index.py`) — ezekhez van elég
  hosszú, éves valós idősor. Az akkumulátorár, töltőinfra, EV-vám és CO2-
  szabályozás — a BEV-térnyerés további valószínű mozgatórugói — nincsenek
  visszatesztelve, mert nincs hozzájuk elég hosszú történeti adat.
- Az üzemanyagár bevonása a korrelációt javította (+0,04 → +0,15/+0,17), a
  találati arányt viszont rontotta (hibrid vs. ICE: 52%, a véletlen szintje) —
  a riport "Értelmezés" része ezt már a tényleges számokból írja.
- A "megfigyelt piaci momentum" tag (`engine.py`) szándékosan **ki van
  hagyva** a backtestből, mert ugyanabból a KSH-idősorból számol, amit itt
  tényleges kimenetként használunk — bevonása körkörös lenne.

Ez a backtest tehát nem "bizonyítja", hogy a modell jó — inkább őszintén
megmutatja, hogy a jelenlegi kalibráció részben jó irányba mutat, de
messze nem pontos, és pontosan megnevezi, mely tényezők visszatesztelése
hiányzik még.

## Bővítési pontok

- **Valós márkánkénti bontás** a jelenlegi márkakategória-szintek helyett,
  ha van regisztrációs adat.
- **Finomabb évjárat-sávok**, ha az adat lehetővé teszi.
- **További tényezők** (pl. nyersanyagárak — lítium, nikkel — vagy KSH CPI-alapú
  inflációs tényező) felvétele a `factors.json`-be és érzékenységi
  együtthatók hozzáadása a `segments.json`-ben.
- **HTML/dashboard kimenet** a markdown helyett/mellett (pl. Claude Artifact),
  ha vizuális, interaktív riport is kell.
