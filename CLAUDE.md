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

### Momentum terms are separate from scenario factors
`engine.py` adds two "observed market momentum" terms on top of the scenario score, deliberately
NOT scenario-dependent (they represent what's already happening, not a hypothesis):
- `load_momentum()` — drivetrain-level, from KSH stock CAGR (`data/jarmuallomany.json`),
  `MOMENTUM_WEIGHT = 0.15`, capped at `MOMENTUM_CAP_PCT = 50`.
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
headline values (no +/- prefix) and `fmt()` only for genuine deltas.

### Backtesting is intentionally narrow
`backtest.py` only validates the 3 factors with enough historical depth (`financing_cost`,
`purchasing_power`, `consumer_sentiment`) against actual KSH stock-share changes 2003-2024, and
deliberately excludes the momentum term to avoid circularity (momentum is itself derived from the
same stock data being predicted). Current results (~+0.05 correlation, 64% hit rate, n=22) are
weak-but-directionally-consistent — report this honestly rather than overstating validation
coverage when extending it.

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
  `note` mezőjét).

## Report/file naming convention
`reports/` filenames are prefixed by report type: `riport_` (scenario-based), `szegmens_riport_`,
`uzemanyag_riport_`, `makro_riport_`, `toltoinfra_riport_`, `forgalomba_riport_`,
`szentiment_riport_`, `realjovedelem_riport_`, plus `backtest_riport.md` and the always-overwritten
`DIGEST.md` one-pager (source for the macOS notification text via `digest_report.py`).
</content>
