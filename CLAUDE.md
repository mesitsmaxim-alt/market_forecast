# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Hungarian automotive market forecasting and automated reporting system. It combines a
scenario-based scoring model (estimated factors like oil price, battery cost, EV tariffs)
with real-data-calibrated factors and pure real-data trend reports (KSH, MNB, Eurostat, EAFO),
and publishes a summary dashboard. Git repo, pushed to the PUBLIC GitHub repo `mesitsmaxim-alt/market_forecast`; `logs/`, `__pycache__/` and the re-downloaded `data/_raw_*` files are gitignored (`data/raw_eafo/` is a manual export and IS tracked).

## Running things

Run the full pipeline (fetch → calibrate → report → dashboard → backtest → digest → git commit+push → notify):
```bash
./run_pipeline.sh
```
This is also what the monthly launchd job (`~/Library/LaunchAgents/com.maxim.marketforecast.pipeline.plist`,
day 1 @ 10:00) runs. Logs go to `logs/run_<timestamp>.log`; launchd's own stdout/stderr go to
`logs/launchd.out.log` / `logs/launchd.err.log`.

Individual stages can be run standalone (see README.md "Futtatás" section for the full command
list per data source) — each fetcher writes one `data/*.json` file, and each `*_report.py`
consumes it to write a markdown report into `reports/`.

Use `python3`, not `python` — installed via the python.org 3.14 build, with openpyxl, xlrd,
and beautifulsoup4 added via `python3 -m pip install`.

Fetchers use `curl` via `subprocess.run()`, never `urllib` — the python.org macOS build doesn't
see the system Keychain certs, so urllib SSL verification fails.

## Architecture

### Three kinds of "factor" feed the same engine
`engine.py::compute_segments()` scores every (drivetrain × brand_tier × year_bucket × scenario)
combination in `config/segments.json` against every factor in `config/factors.json`, using each
segment's per-factor `sensitivity` coefficient (-1..+1), summed and weighted.

- **Calibrated factors** (`oil_price`, `charging_infra`, `financing_cost`, `consumer_sentiment`,
  `purchasing_power`) — `calibrate_factors.py` overwrites their `pesszimista/alap/optimista`
  scenario values in `config/factors.json` from real data in `data/*.json`, every pipeline run.
  The `alap` (base) scenario is always the actual latest observed trend; pesszimista/optimista
  are that trend ± a fixed band. `oil_price` in particular is calibrated from the LIVE
  `data/uzemanyagar_elo.json` (see below) so it never goes stale.
- **Manual-source factors** (`battery_cost`, `ev_tariffs`, `co2_regulation`) — also overwritten
  by `calibrate_factors.py`, but from hand-maintained, source-cited files (`data/akkuar.json` —
  BNEF yearly survey; `data/ev_vamok.json` — EU countervailing duties + `events` with estimated
  `impact_pp`; `data/co2_szabalyozas.json` — EU fleet CO2 milestones, `proposals` NOT counted until
  adopted). No machine-readable source exists for these. `staleness_warning()` flags files whose
  `updated` date exceeds `STALE_DAYS`. Dashboard: `calibrated: "manual"` → "◐ kézi forrás" badge
  (`"auto"` for fetcher-backed ones, via `MANUAL_SOURCE_FACTORS` / `CALIBRATED_FACTORS` in
  `build_dashboard.py`). When updating these files, verify the facts by web search first.

### Scenario bands come from each factor's own volatility
For the 5 auto-calibrated factors, `calibrate_factors.py` sets pesszimista/optimista = alap ± the
population std of the factor's historical 12-month changes over `VOL_WINDOW_YEARS = 10`
(`hist_spread()` and the `*_spread()` helpers): fuel from the Eurostat HICP fuel index
(`fetchers/fetch_uzemanyag_index.py` → `data/uzemanyag_index.json`), base rate monthly 12m
changes, charging infra only the last `CHARGING_VOL_WINDOW_Q = 12` quarters (the 2020-21 small-base
growth would blow the std up to ~57), sentiment on 3-month averages, real wage year-to-year
differences. The old fixed `*_SPREAD_*` constants are only fallbacks (< `VOL_MIN_POINTS` history);
the 3 manual factors keep fixed bands. Each factor's `note` states its band and basis.
`consumer_sentiment.alap` compares the latest 3-month average with the same 3 months a year
earlier (a single noisy survey month used to swing it, e.g. +13.5 → +5.5 in one update).

### Momentum terms are separate from scenario factors
`engine.py` adds two "observed market momentum" terms on top of the scenario score, deliberately
NOT scenario-dependent (they represent what's already happening, not a hypothesis):
- `load_momentum()` — drivetrain-level. PRIMARY source: the change of each drivetrain's SHARE
  of new car registrations (pp/year, avg over `MOMENTUM_WINDOW_YEARS = 3`), from Eurostat
  `road_eqr_carpda` via `fetchers/fetch_uj_hajtas.py` → `data/uj_hajtas.json` (annual, HU, 2020+;
  separates PHEV from HEV; Eurostat's "hybrid" includes mild hybrids). `MOMENTUM_WEIGHT = 0.15`,
  normalized by `MOMENTUM_CAP_PP = 10`. It replaced the KSH stock CAGR (2026-10-01) because stock
  growth of small-base categories measured a base effect, not demand (BEV +42%/yr while 2% of
  stock had become the single biggest BEV driver). The stock CAGR (`load_stock_momentum()`,
  `MOMENTUM_CAP_PCT = 50`) remains only as a fallback if `uj_hajtas.json` is missing; the driver
  label tells which one ran ("új autók részesedése" vs "KSH állomány").
- `load_registration_momentum()` — brand_tier-level, from KSH quarterly new-registration YoY
  (`data/forgalomba.json`), `REG_MOMENTUM_WEIGHT = 0.1`, capped at `REG_MOMENTUM_CAP_PCT = 40`.

The weights were deliberately reduced (from 0.4) after a quality review found momentum could
dominate the scenario signal — see README.md "minőség ellenőrzés" section before changing them.

### Live vs. frozen data: fuel prices
`data/uzemanyagar_elo.json` (via `fetchers/fetch_uzemanyag_elo.py`, scraping holtankoljak.hu) is
the LIVE, always-current fuel price source and is what `oil_price` calibration and the dashboard
headline/sparkline use. `data/uzemanyagar.json` (KSH regional table, via `fetch_uzemanyagar.py`)
is historical/regional context only — it is NOT auto-updated as often and must never be used as
the primary "current price" source. When touching fuel price logic, keep the dashboard's
headline number and its sparkline's last point sourced from the same value (`uzemanyagar_elo`),
per a past bug where they diverged.

### Dashboard build is a two-step, non-publishing process
`dashboard/build_dashboard.py` reads all `data/*.json` + the engine output, writes
`dashboard/dashboard_data.json`, and injects it into `dashboard/template.html` (replacing the
`__DASHBOARD_DATA__` placeholder) to produce `dashboard/dashboard.html`. This script never
publishes anything — publishing to the live Claude Artifact URL is a manual step done from an
interactive Claude Code session (Artifact tool, update the existing URL). Data refresh is fully
automated (monthly via launchd); publishing is intentionally a manual confirmation step.

Every "real data" card in `template.html` needs: a plain-language `desc` line, `sparkLabels`
(period anchors under the mini chart), and — where the metric's scale isn't self-evident (e.g.
the -100..+100 consumer sentiment balance index) — a `scaleNote`. Use `fmtPlain()` for standalone
headline values (no +/- prefix) and `fmt()` only for genuine deltas. Every displayed number must go
through `fmt`/`fmtPlain`/`fmtInt` (all built on `huNum()`: Hungarian decimal comma, space thousands
grouping incl. 4-digit numbers, real minus sign) — never print a raw number or `toFixed()` into
visible text (`toFixed` is only for SVG coordinates / CSS widths). The page is PUBLIC: no internal
maintenance text (script names, "ask Claude", launchd) in visible copy — that belongs in the data
files' `note` fields or here.

### Backtesting is intentionally narrow
`backtest.py` only validates the 4 factors with enough historical depth (`financing_cost`,
`purchasing_power`, `consumer_sentiment`, and since 2026-10-01 `oil_price` via the Eurostat HICP fuel
index annual average) against actual KSH stock-share changes 2003-2025, and
deliberately excludes the momentum term (it measures the same market shift being predicted, and the
Eurostat new-registration data only starts in 2020). Results as of 2026-10-01 (n=23): BEV vs ICE
corr +0.15, hit 61%; Hybrid vs ICE corr +0.17, hit 52% (= chance). Adding fuel price raised
correlation (+0.04 → ~+0.16) but lowered hit rate. The report's "Értelmezés" is generated from the
numbers (no fixed "better than chance" claim) — keep it that way and report results honestly.

### Segment sensitivities
`config/segments.json` defines drivetrains (ICE/HEV/PHEV/BEV), brand_tiers (tomeggyarto/premium/
budget/kinai_belepo, each with an `example_brands` list used for momentum weighting), and
year_buckets (uj/fiatal_hasznalt/idosebb_hasznalt) — each carries a `sensitivity` dict keyed by
factor name. `purchasing_power` is the one factor where a segment intentionally gets a *negative*
sensitivity (idosebb_hasznalt: -0.2) to model income effect pulling demand toward pricier
segments, not just uniformly lifting everything — keep this asymmetry in mind if adding new
factors with similar income-effect dynamics.

### Dashboard: futás-történet, teljes idősorok és trendvetítés
A dashboard 3 fülre van bontva (`dashboard/template.html`, `data-tabpanel="overview|history|forecast"`,
tab-váltás kliensoldali JS-sel, nincs reload):
- **Történet fül**: kétféle "múlt" van, és nem szabad összekeverni őket. (1) A nyers KSH/MNB/Eurostat
  idősorok (`fuel_shares_series`, `*_series_full` kulcsok `build_real_snapshot()`-ban) évekre/évtizedekre
  visszanyúlnak, és a fetcherek minden futáskor a teljes forrás-idősort újratöltik — ezekből azonnal
  teljes visszatekintés adható. (2) A modell SAJÁT kimenetei (tényező-értékek, szegmens-pontszámok)
  viszont sosem voltak archiválva a 2026-09-18 előtti bevezetésig — a `data/history/snapshots.jsonl`
  (egy JSON sor / `build_dashboard.py` futás, `append_history_snapshot()`) mostantól gyűlik, és a
  Történet fülön addig egy "gyűjtés folyamatban" üzenet jelenik meg (`run_history.length < 3`), amíg
  nincs elég futás a trend megjelenítéséhez. Ne próbáld visszamenőleg pótolni — nincs mit, a korábbi
  futások kimenetei nem lettek elmentve.
- **Előrejelzés fül**: a valós mutatókra (`forecast.py::linreg_forecast()`) sima stdlib OLS lineáris
  regresszió fut a teljes idősoron, ±1 reziduál-szórás sávval — szándékosan nem ML-modell, mert a cél a
  jelenlegi trend irányának durva becslése, nem pontos predikció (lásd a modul docstringjét). A
  szegmens-pontszámokhoz NEM ez ad előrejelzést: ott a meglévő pesszimista/alap/optimista forgatókönyv-
  sávot (`drivetrain_summary[].pesszimista/optimista`, `agg()` most mindhárom forgatókönyvet
  aggregálja, nem csak az alapot) jelenítjük meg explicit "forgatókönyv-alapú, nem statisztikai"
  előrejelzésként — ez elkerüli, hogy két egymásnak ellentmondó predikciós logika legyen egymás
  mellett. A 3 pontos (vagy annál rövidebb) `uzemanyagar_elo` sorozatra emiatt nincs regresszió
  (`forecast_card()` None-t ad vissza 3 pontnál kevesebb adatra), az `oil_price` faktor sávja adja az
  irányt helyette.

### Dashboard: forgatókönyv-váltó, hőtérkép, "Mi változott?"
- `build_engine_summary()` a `segments` kulcson mind a 48 szegmenst átadja mindhárom
  forgatókönyvre (`scores`/`dirs`); az Áttekintés forgatókönyv-váltója, a hőtérkép és a
  nyertes/vesztes listák kliensoldalon ebből számolnak. A `top_winners`/`top_losers` (alap)
  a digest miatt maradt meg.
- `load_history()` NAPONTA EGY pillanatképet ad vissza (a nap utolsó futását); a
  `snapshots.jsonl` nyers archívum továbbra is minden futást megtart. A `main()` a mai
  napot kiveszi a `run_history`-ból, a Történet fül a mostani futást a végére fűzi.
- `build_changes()` az előző NAPI futáshoz viszonyít (szegmens-irányok, alap tényezők, valós
  fő mutatók) → `changes` kulcs, irányváltások elöl.

### Dashboard: "Hogyan számol a modell?" blokk
A 2. szekció tetején egy natív `<details>` blokk magyarázza a szegmens-pontszámokat (magyar piac,
48 szegmens, 8 tényező forrással és HU/EU-globális hatókörrel, érzékenység × változás, évjárat-
súlyok, KSH-lendület, korlátok). Minden száma a `build_methodology()`-ból jön (`methodology`
kulcs): a tényező-források a `FACTOR_SOURCES` dictből (új tényezőnél ide is fel kell venni!), az
évjárat-súlyok a `segments.json`-ból, a lendület-súlyok az `engine.py` konstansaiból, a backtest a
`data/backtest.json`-ból. Ezért a `run_pipeline.sh` a `backtest.py`-t a dashboard ELŐTT futtatja.

A három sávdiagram-kártya alján lévő "Következtetés" szövegeket a template SZABÁLYALAPÚAN
generálja (`conclDrivetrain` / `conclBrand` / `conclYear`) a kiválasztott forgatókönyv
pontszámaiból és az aggregátumok `drivers` mezőjéből (tényezőnkénti átlagos hozzájárulás
pontban, évjárat-súllyal — az összegük kiadja a pontszámot; `build_engine_summary()` számolja).
Nem kézzel írt szöveg: havonta és forgatókönyv-váltáskor magától frissül. Új tényezőnél a
`DRIVER_NAMES` listába (template) is fel kell venni a rövid nevét. ±5 pont alatti értékeknél
a szöveg "semleges tartomány"-t mond, nem rangsorol.

FONTOS: a márkakategória- és évjárat-aggregátumok `score`-ja a csoport szegmenseinek EGYSZERŰ
átlaga (minden hajtás egyforma súllyal) — ez a piac ~91%-át adó belső égésűt alulsúlyozza, ezért
lehet a kártya pozitív, miközben a csoport ICE-szegmensei negatívak. Mellette a
`market_weighted` mező a hajtásokat a valós piaci arányuk szerint súlyozza, ÉVJÁRAT-SÁVONKÉNT
más alapon (`drivetrain_market_weights()`, `YEAR_BUCKET_MARKET`): új = a legutóbbi év új eladásai
(Eurostat, `uj_hajtas.json`), fiatal használt (3–5 év) = a mai év − 5 … − 3 évek új eladásai,
idősebb használt = a mostani KSH-állomány (a hibridet ott a legkorábbi Eurostat-év PHEV/HEV
arányával bontjuk). Eurostat-adat híján minden sáv a KSH-állományra esik vissza. Közelítés: a
használt piacon sok az import, amelynek összetétele eltérhet a hazai új eladásokétól. A dashboard
mindkét számot mutatja, a "Mi változott?" és a futástörténet az egyszerű átlagot követi
(összevethetőség miatt).

### Piaci hírek ("Amit a piac mond" fül) és legkeresettebb modellek
- **Hírek** (`fetchers/fetch_hirek.py` → `data/hirek.json` → `hirek_report.py`): 3 magyar RSS-forrás
  (Vezess.hu, Portfolio.hu, Világgazdaság), curl-lal lekérve, `xml.etree.ElementTree`-vel parszolva
  (stdlib, nincs új függőség). A **Totalcar.hu szándékosan NINCS bent** — kérésre eltávolítva
  (2026-09-18), mert a feedje túlnyomórészt teszt/bulvár/baleseti tartalom volt, és még szigorú
  kulcsszó-szűréssel is átcsúszott rajta clickbait cikk. A **nemzetközi jelöltek (Automotive News
  Europe, Reuters Autos) nyilvános RSS-je nem elérhető** (bot-védett/megszűnt, ellenőrizve
  2026-09-18-án) — ha ez változik, ide vehető fel egy új `FEEDS` bejegyzés. Két szűrő fut EGYÜTT,
  csak a CÍMBEN (a `<description>` mező bevonása korábban politikai/gazdasági hírekkel szennyezte a
  listát): (1) `is_relevant()` — kizárólag összetett, egyértelműen autó-specifikus kifejezés fogadható
  el (`MARKET_TERMS`, pl. "autóipar", "autógyár"), szándékosan NEM elég önmagában a "piac"/"eladás"/
  "beruházás" szó (ezek túl tágak: "kukoricapiac", "eladó a sztár autója", egy teljesen más iparági
  beruházás); (2) `is_clickbait()` — kizárja a szenzációhajhász/bulvár hangvételű címeket
  (felkiáltójel, kérdőjeles rájátszás, `CLICKBAIT_MARKERS` szólista, pl. "elképesztő", "óriási",
  "döbbenetes") — ez a KOMOLY HANGVÉTEL követelménye miatt van, és tudatosan kizár egy egyébként
  ténylegesen piaci hírt is, ha a cím bulvár-stílusú (kérésre így, ld. felhasználói visszajelzés).
  Ez a szigorú, kettős szűrés jelentősen csökkenti a találatok számát (jellemzően 2-6 cikk/futás) —
  ez szándékos, a mennyiség helyett minőséget/komolyságot priorizál. Durva heurisztika, nem
  szemantikai elemzés — occasionally túl szigorú vagy túl enyhe lehet egy-egy határeset címnél.
- **Legkeresettebb modellek** (`data/top_modellek.json`): NINCS hivatalos, ingyenes, gépileg
  lekérdezhető magyar forrás modell-szintű (nem csak márka-szintű) új autó eladási adatra — a KSH
  STADAT táblái csak gyártmány/márka szerint bontanak. Az egyetlen reális forrás a jarmuipar.hu
  havonta megjelenő "Top X" cikke (Datahouse-adatok alapján), de ez FOLYÓ SZÖVEG, nem táblázat/lista
  (a cikk törzsében van egy számozott felsorolás, de címke/konténer nélkül, a formátum és a címadás
  is hónapról hónapra változik: Top 50/75/100/150) — ezért ez SZÁNDÉKOSAN kézi adatbevitel, nincs
  hozzá fetcher és nincs bekötve a `run_pipeline.sh`-ba. Frissítéshez: amikor megjelenik egy új
  jarmuipar.hu cikk, olvasd ki a modell-szintű Top listát és írd át a `rows` tömböt (lásd a fájl
  `note` mezőjét). A forrás KÖZÖS személyautó + kishaszonjármű lista: minden sor kap egy `type`
  mezőt (`szemelyauto` / `kisbusz` / `kishaszon`, a cikk jelölése alapján). A dashboard "Csak
  személyautók" szűrője csak a `kishaszon`-t (N1: pickup, furgon) rejti el; a `kisbusz` (pl.
  Tourneo Custom) M1, a KSH is személyautónak számolja, ezért látható marad. A látogatóknak
  szóló szöveg a `public_note`, a `note` belső karbantartási útmutató — azt NE jelenítsd meg.
  A fül 45 napnál régebbi `updated` esetén elavulás-figyelmeztetést mutat.
  A `previous` blokk az előző havi cikk TELJES Top 100-as listája: ebből számolja a
  `build_top_modellek()` a helyezés-változást és az utolsó havi darabszámot (`increment_label`,
  pl. "aug."); havi frissítéskor a mostani cikk teljes listája kerül át ide. A márkakategória a
  `segments.json` `example_brands`-ából + a `DISPLAY_BRAND_TIERS` (csak megjelenítés; a
  `segments.json`-t szándékosan NEM bővítjük, mert az hajtja a márka-momentumot). A piaci
  részesedés nevezője a `market_total_units` (személyautó + kishaszonjármű együtt).

## Report/file naming convention
`reports/` filenames are prefixed by report type: `riport_` (scenario-based), `szegmens_riport_`,
`uzemanyag_riport_`, `makro_riport_`, `toltoinfra_riport_`, `forgalomba_riport_`,
`szentiment_riport_`, `realjovedelem_riport_`, plus `backtest_riport.md` and the always-overwritten
`DIGEST.md` one-pager (source for the macOS notification text via `digest_report.py`).
</content>
