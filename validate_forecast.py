#!/usr/bin/env python3
"""
A modell előrejelzéseinek automatikus, determinisztikus ellenőrzése (validáció).

Ez a hierarchikus validációs rendszer ALSÓ szintje: olcsó, reprodukálható
invariáns- és konzisztencia-ellenőrzések, amelyek minden pipeline-futásban
lefutnak, és CRITICAL hibánál nem-nulla kóddal lépnek ki - így a
run_pipeline.sh nem commitol / push-ol hibás előrejelzést a publikus repóba.
A mélyebb (forrás-, hihetőségi és statisztikai) auditot a /validate-forecast
Claude Code skill és a .claude/agents/forecast-* subagentek végzik, ennek a
scriptnek a kimenetére építve.

Két fázis, mert a build_dashboard.py a history-snapshotot a dashboard-adattal
együtt írja:
  --stage pre   a kalibráció + backtest után: config/factors.json,
                config/segments.json, engine.compute_segments() friss kimenete,
                kézi forrásfájlok elavulása, backtest.json
  --stage post  a build_dashboard.py után: dashboard/dashboard_data.json,
                data/history/snapshots.jsonl, dashboard/template.html
  --stage all   mindkettő (alapértelmezett, kézi futtatáshoz)

Súlyosság: CRITICAL (blokkolja a pipeline-t) / WARN (csak a riportba kerül).
Szándékosan NEM invariáns: pesszimista <= alap <= optimista. A forgatókönyv-
tengely az EV-térnyerés iránya, nem a gazdaságé, így pl. az ICE-szegmensek
pontszáma az optimista ágon a legalacsonyabb (ld. README). Ami igaz: az alap
mindig a két szélső forgatókönyv KÖZÖTT van (a pontszám lineáris a deltákban).

Használat:
    python3 validate_forecast.py [--stage pre|post|all]
Kimenet:
    data/validation.json        (fázisonkénti eredmények, a mai napra)
    reports/validacio_riport.md (mindig felülíródik)
    exit 1, ha az adott fázisban bármelyik CRITICAL ellenőrzés elbukik
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from engine import (  # noqa: E402
    compute_segments, classify, load_config, SCENARIOS,
    MOMENTUM_WEIGHT, REG_MOMENTUM_WEIGHT,
)
from calibrate_factors import STALE_DAYS, staleness_warning  # noqa: E402

DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
DASHBOARD_DIR = ROOT / "dashboard"
REPORTS_DIR = ROOT / "reports"
VALIDATION_PATH = DATA_DIR / "validation.json"
REPORT_PATH = REPORTS_DIR / "validacio_riport.md"
HISTORY_PATH = DATA_DIR / "history" / "snapshots.jsonl"

N_FACTORS = 8  # új tényezőnél frissíteni kell
N_SEGMENTS = 48  # 4 hajtás x 4 márkakategória x 3 évjárat-sáv
SCORE_ABS_MAX = 2.0  # ennél nagyobb |pontszám| számítási hibára utal (ma max ~1,2)
DRIVER_SUM_TOL_PTS = 0.1  # a drivers pontjai 2 tizedesre kerekítettek
BAND_TOL = 0.15  # a tényező-sávok 0,1-re kerekítettek
WEIGHT_SUM_TOL = 0.002
TOP_MODELLEK_STALE_DAYS = 45  # ugyanaz, mint a dashboard figyelmeztetése
JUMP_SCORE = 0.3  # összesítő pontszám napi változása, ami fölött WARN
JUMP_BAND_MULT = 2.0  # tényező alap-értékének változása a sávja hányszorosáig normális

CRITICAL, WARN = "CRITICAL", "WARN"


class Checks:
    def __init__(self, stage: str):
        self.stage = stage
        self.items: list[dict] = []

    def add(self, check_id: str, severity: str, ok: bool, message: str, details=None):
        self.items.append({
            "id": check_id, "severity": severity, "ok": bool(ok),
            "message": message, "details": details or [],
        })

    def status(self) -> str:
        if any(not c["ok"] and c["severity"] == CRITICAL for c in self.items):
            return "FAIL"
        if any(not c["ok"] for c in self.items):
            return "WARN"
        return "PASS"


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def between(a, lo, hi, tol=1e-9) -> bool:
    return min(lo, hi) - tol <= a <= max(lo, hi) + tol


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- pre stage

def check_factors(c: Checks):
    factors = load_json(CONFIG_DIR / "factors.json")["factors"]
    c.add("factors.count", CRITICAL, len(factors) == N_FACTORS,
          f"{len(factors)} tényező a config/factors.json-ban (elvárt: {N_FACTORS})")

    bad_values, bad_order, bad_band = [], [], []
    for key, f in factors.items():
        sc = f.get("scenarios", {})
        if not all(is_num(sc.get(s)) for s in SCENARIOS):
            bad_values.append(f"{key}: {sc}")
            continue
        p, a, o = (sc[s] for s in SCENARIOS)
        if not between(a, p, o):
            bad_order.append(f"{key}: pesszimista={p}, alap={a}, optimista={o}")
        # a sáv szimmetrikus az alap körül; ha a note megnevezi, annak kell lennie
        if abs(abs(o - a) - abs(a - p)) > BAND_TOL:
            bad_band.append(f"{key}: aszimmetrikus sáv ({p} / {a} / {o})")
        m = re.search(r"Forgatókönyv-sáv: ±([\d.]+)", f.get("note", ""))
        if m and abs(abs(o - a) - float(m.group(1))) > BAND_TOL:
            bad_band.append(f"{key}: a note ±{m.group(1)} sávot ír, a tényleges ±{abs(o - a):.1f}")

    c.add("factors.values", CRITICAL, not bad_values,
          "minden tényezőnek mindhárom forgatókönyv-értéke véges szám", bad_values)
    c.add("factors.alap_between", CRITICAL, not bad_order,
          "a tényezők alap értéke a pesszimista és az optimista között van", bad_order)
    c.add("factors.band", CRITICAL, not bad_band,
          "a tényező-sávok szimmetrikusak, és egyeznek a note-ban leírttal", bad_band)


def check_segment_config(c: Checks):
    _, seg = load_config()
    bad = []
    for group in ("drivetrains", "brand_tiers"):
        for key, item in seg[group].items():
            for fk, v in item.get("sensitivity", {}).items():
                if not (is_num(v) and -1 <= v <= 1):
                    bad.append(f"{group}.{key}.{fk} = {v}")
    for key, yb in seg["year_buckets"].items():
        for fk, v in yb.get("extra_sensitivity", {}).items():
            if not (is_num(v) and -1 <= v <= 1):
                bad.append(f"year_buckets.{key}.{fk} = {v}")
        if not (is_num(yb.get("weight")) and yb["weight"] > 0):
            bad.append(f"year_buckets.{key}.weight = {yb.get('weight')}")
    c.add("segments.sensitivity_range", CRITICAL, not bad,
          "az érzékenységek −1..+1 között, az évjárat-súlyok pozitívak", bad)


def check_engine(c: Checks):
    results, _ = compute_segments()
    _, seg = load_config()
    yb_weight = {k: v["weight"] for k, v in seg["year_buckets"].items()}

    c.add("engine.count", CRITICAL, len(results) == N_SEGMENTS,
          f"{len(results)} szegmens (elvárt: {N_SEGMENTS})")

    bad_values, too_big, bad_order, bad_sum, bad_momentum = [], [], [], [], []
    for r in results:
        name = f"{r.drivetrain}/{r.brand_tier}/{r.year_bucket}"
        if not all(is_num(r.scores.get(s)) for s in SCENARIOS):
            bad_values.append(f"{name}: {r.scores}")
            continue
        for s in SCENARIOS:
            if abs(r.scores[s]) > SCORE_ABS_MAX:
                too_big.append(f"{name} [{s}]: {r.scores[s]:+.3f}")
            raw_sum = sum(v for _, v in r.drivers[s]) * yb_weight[r.year_bucket]
            if abs(raw_sum - r.scores[s]) > 1e-9:
                bad_sum.append(f"{name} [{s}]: drivers {raw_sum:+.4f} vs pontszám {r.scores[s]:+.4f}")
            for label, v in r.drivers[s]:
                if label.startswith("Megfigyelt piaci momentum"):
                    cap = REG_MOMENTUM_WEIGHT if "forgalomba helyezés" in label else MOMENTUM_WEIGHT
                    if abs(v) > cap + 1e-9:
                        bad_momentum.append(f"{name} [{s}] {label}: {v:+.3f} (max ±{cap})")
        p, a, o = (r.scores[s] for s in SCENARIOS)
        if not between(a, p, o):
            bad_order.append(f"{name}: {p:+.3f} / {a:+.3f} / {o:+.3f}")

    c.add("engine.values", CRITICAL, not bad_values, "minden szegmens-pontszám véges szám", bad_values)
    c.add("engine.score_range", CRITICAL, not too_big,
          f"minden |pontszám| ≤ {SCORE_ABS_MAX}", too_big)
    c.add("engine.drivers_sum", CRITICAL, not bad_sum,
          "a tényezőnkénti hozzájárulások összege × évjárat-súly = pontszám", bad_sum)
    c.add("engine.momentum_cap", CRITICAL, not sorted(set(bad_momentum)),
          f"momentum-tagok: hajtás ≤ ±{MOMENTUM_WEIGHT}, márka ≤ ±{REG_MOMENTUM_WEIGHT}",
          sorted(set(bad_momentum)))
    c.add("engine.alap_between", CRITICAL, not bad_order,
          "minden szegmens alap pontszáma a pesszimista és az optimista között van", bad_order)


def check_staleness(c: Checks):
    msgs = []
    for key in STALE_DAYS:
        path = DATA_DIR / f"{key}.json"
        if not path.exists():
            msgs.append(f"hiányzik: data/{key}.json")
            continue
        w = staleness_warning(load_json(path), key)
        if w:
            msgs.append(w)
    c.add("sources.manual_stale", WARN, not msgs,
          "a kézi forrásfájlok (akkuár, EV-vámok, CO2) a STALE_DAYS küszöbön belül frissültek", msgs)

    path = DATA_DIR / "top_modellek.json"
    if path.exists():
        updated = dt.date.fromisoformat(load_json(path)["updated"])
        age = (dt.date.today() - updated).days
        c.add("sources.top_modellek_stale", WARN, age <= TOP_MODELLEK_STALE_DAYS,
              f"a data/top_modellek.json {age} napos (küszöb: {TOP_MODELLEK_STALE_DAYS} nap)")


def check_backtest(c: Checks):
    path = DATA_DIR / "backtest.json"
    if not path.exists():
        c.add("backtest.exists", CRITICAL, False, "hiányzik a data/backtest.json")
        return
    bt = load_json(path)
    today = dt.date.today().isoformat()
    c.add("backtest.fresh", WARN, bt.get("generated") == today,
          f"a backtest ma futott (generated: {bt.get('generated')})")
    weak = [f"{r['label']}: korreláció {r['correlation']:+.3f}, találati arány {r['hit_rate']:.0%} (n={r['n']})"
            for r in bt.get("comparisons", [])
            if r.get("correlation") is None or r["correlation"] < 0 or r["hit_rate"] < 0.5]
    c.add("backtest.quality", WARN, not weak,
          "a backtest korrelációja nem negatív, a találati arány legalább 50%", weak)


def run_pre(c: Checks):
    check_factors(c)
    check_segment_config(c)
    check_engine(c)
    check_staleness(c)
    check_backtest(c)


# --------------------------------------------------------------- post stage

def iter_forecast_cards(real: dict):
    """(útvonal, kártya) párok a real snapshot összes *forecast kulcsából."""
    for section, data in real.items():
        if not isinstance(data, dict):
            continue
        for key, val in data.items():
            if not key.endswith("forecast"):
                continue
            if isinstance(val, dict) and "points" in val:
                yield f"real.{section}.{key}", val
            elif isinstance(val, dict):
                for sub, card in val.items():
                    if isinstance(card, dict):
                        yield f"real.{section}.{key}.{sub}", card


def check_dashboard(c: Checks):
    d = load_json(DASHBOARD_DIR / "dashboard_data.json")
    today = dt.date.today().isoformat()

    c.add("dashboard.fresh", WARN, d.get("generated") == today,
          f"a dashboard_data.json ma készült (generated: {d.get('generated')})")

    # --- szerkezet
    segs = d.get("segments", [])
    combos = {(s["drivetrain"], s["brand_tier"], s["year_bucket"]) for s in segs}
    c.add("dashboard.segments_count", CRITICAL, len(segs) == N_SEGMENTS and len(combos) == N_SEGMENTS,
          f"{len(segs)} szegmens, {len(combos)} egyedi kombináció (elvárt: {N_SEGMENTS})")
    c.add("dashboard.factors_count", CRITICAL, len(d.get("factors", [])) == N_FACTORS,
          f"{len(d.get('factors', []))} tényező (elvárt: {N_FACTORS})")
    cov = d.get("coverage", {})
    c.add("dashboard.coverage", CRITICAL,
          cov.get("n_calibrated", 0) + cov.get("n_manual", 0) == cov.get("n_factors"),
          f"lefedettség: {cov.get('n_calibrated')} automata + {cov.get('n_manual')} kézi "
          f"= {cov.get('n_factors')} tényező")

    # --- szegmensek és összesítők: értékek, sorrend, drivers-összeg, irány-címke
    bad_values, bad_order, bad_sum, bad_dir = [], [], [], []
    for s in segs:
        name = f"{s['drivetrain']}/{s['brand_tier']}/{s['year_bucket']}"
        sc = s.get("scores", {})
        if not all(is_num(sc.get(k)) for k in SCENARIOS):
            bad_values.append(f"{name}: {sc}")
            continue
        if not between(sc["alap"], sc["pesszimista"], sc["optimista"]):
            bad_order.append(name)
        for k in SCENARIOS:
            total = sum(x["points"] for x in s["drivers"][k])
            if abs(total - sc[k] * 100) > DRIVER_SUM_TOL_PTS:
                bad_sum.append(f"{name} [{k}]: drivers {total:+.2f} vs pontszám {sc[k] * 100:+.2f}")
            if s["dirs"][k] != classify(sc[k]):
                bad_dir.append(f"{name} [{k}]: '{s['dirs'][k]}' vs '{classify(sc[k])}'")

    for group in ("drivetrain_summary", "brand_summary", "year_summary"):
        for r in d.get(group, []):
            name = f"{group}.{r['key']}"
            sc = {"pesszimista": r.get("pesszimista"), "alap": r.get("score"), "optimista": r.get("optimista")}
            if not all(is_num(v) for v in sc.values()):
                bad_values.append(f"{name}: {sc}")
                continue
            if not between(sc["alap"], sc["pesszimista"], sc["optimista"]):
                bad_order.append(name)
            if r["dir"] != classify(sc["alap"]):
                bad_dir.append(f"{name}: '{r['dir']}' vs '{classify(sc['alap'])}'")
            for k in SCENARIOS:
                if r["dirs"][k] != classify(sc[k]):
                    bad_dir.append(f"{name} [{k}]: '{r['dirs'][k]}' vs '{classify(sc[k])}'")
                total = sum(x["points"] for x in r["drivers"][k])
                if abs(total - sc[k] * 100) > DRIVER_SUM_TOL_PTS * 2:
                    bad_sum.append(f"{name} [{k}]: drivers {total:+.2f} vs pontszám {sc[k] * 100:+.2f}")

    c.add("dashboard.values", CRITICAL, not bad_values, "minden pontszám véges szám", bad_values)
    c.add("dashboard.alap_between", CRITICAL, not bad_order,
          "az alap pontszám a pesszimista és az optimista között van (szegmensek, összesítők)", bad_order)
    c.add("dashboard.drivers_sum", CRITICAL, not bad_sum,
          "a drivers pontjainak összege = pontszám × 100 (szegmensek, összesítők)", bad_sum)
    c.add("dashboard.dir_labels", CRITICAL, not bad_dir,
          "minden irány-címke = classify(pontszám)", bad_dir)

    # --- piaci súlyok
    mw = (d.get("market_weights") or {}).get("weights", {})
    bad_w = [f"{yb}: Σ = {sum(w.values()):.4f}" for yb, w in mw.items()
             if abs(sum(w.values()) - 1) > WEIGHT_SUM_TOL or any(v < 0 for v in w.values())]
    c.add("dashboard.market_weights", CRITICAL, bool(mw) and not bad_w,
          "a piaci súlyok évjárat-sávonként nemnegatívak és 1-re összegződnek", bad_w)

    # --- konzisztencia a forrásfájlokkal
    cfg = load_json(CONFIG_DIR / "factors.json")["factors"]
    diff = []
    for f in d.get("factors", []):
        src = cfg.get(f["key"], {}).get("scenarios")
        if src is None:
            diff.append(f"{f['key']}: nincs a config/factors.json-ban")
            continue
        for s in SCENARIOS:
            if not is_num(f.get(s)) or abs(f[s] - src[s]) > 1e-9:
                diff.append(f"{f['key']} [{s}]: dashboard {f.get(s)} vs config {src[s]}")
    c.add("consistency.factors", CRITICAL, not diff,
          "a dashboard tényező-értékei = config/factors.json", diff)

    bt_path = DATA_DIR / "backtest.json"
    if bt_path.exists():
        bt = load_json(bt_path)
        shown = (d.get("methodology") or {}).get("backtest") or {}
        same = shown.get("comparisons") == bt.get("comparisons")
        c.add("consistency.backtest", CRITICAL, same,
              "a dashboard módszertani blokkjának backtest-eredménye = data/backtest.json")

    # --- élő üzemanyagár: a főszám és a sparkline utolsó pontja ugyanaz (CLAUDE.md)
    u = d["real"]["uzemanyagar"]
    fuel_bad = [f"{k}: főszám {u[f'{k}_last']} vs sparkline utolsó pont {u[f'{k}_series'][-1]}"
                for k in ("benzin", "dizel") if u[f"{k}_last"] != u[f"{k}_series"][-1]]
    c.add("consistency.fuel_headline", CRITICAL, not fuel_bad,
          "üzemanyagár: a főszám = a sparkline utolsó pontja", fuel_bad)

    # --- trendvetítés-kártyák
    bad_cards, bad_share = [], []
    n_cards = 0
    for path, card in iter_forecast_cards(d["real"]):
        n_cards += 1
        pts, lo, hi = card.get("points", []), card.get("lower", []), card.get("upper", [])
        if not pts or not (len(pts) == len(lo) == len(hi)):
            bad_cards.append(f"{path}: eltérő hosszak ({len(pts)}/{len(lo)}/{len(hi)})")
            continue
        if not all(is_num(v) for v in pts + lo + hi):
            bad_cards.append(f"{path}: nem véges érték")
            continue
        if any(not (l <= p <= h) for p, l, h in zip(pts, lo, hi)):
            bad_cards.append(f"{path}: a pont kilóg a sávból")
        if "share" in path and any(not (0 <= p <= 100) for p in pts):
            bad_share.append(f"{path}: {pts}")
    c.add("forecast.cards", CRITICAL, n_cards > 0 and not bad_cards,
          f"{n_cards} trendvetítés-kártya: azonos hossz, alsó ≤ pont ≤ felső", bad_cards)
    c.add("forecast.share_range", CRITICAL, not bad_share,
          "a részesedés-vetítések 0–100% között maradnak", bad_share)

    # --- ugrás az előző napi futáshoz képest (WARN: lehet valós, de nézd meg)
    prev = (d.get("run_history") or [None])[-1]
    if prev:
        jumps = []
        for group in ("drivetrain_summary", "brand_summary"):
            old = {r["key"]: r["score"] for r in prev.get(group, [])}
            for r in d[group]:
                if r["key"] in old and abs(r["score"] - old[r["key"]]) > JUMP_SCORE:
                    jumps.append(f"{group}.{r['key']}: {old[r['key']]:+.3f} → {r['score']:+.3f}")
        for f in d["factors"]:
            old = prev.get("factors", {}).get(f["key"])
            band = abs(f["optimista"] - f["pesszimista"]) / 2
            if old is not None and band > 0 and abs(f["alap"] - old) > JUMP_BAND_MULT * band:
                jumps.append(f"tényező {f['key']}: {old} → {f['alap']} (sáv ±{band:.1f})")
        c.add("history.jumps", WARN, not jumps,
              f"nincs szokatlan ugrás az előző napi futáshoz ({prev.get('date')}) képest", jumps)

    return d


def check_snapshot(c: Checks, d: dict):
    if not HISTORY_PATH.exists():
        c.add("history.snapshot", CRITICAL, False, "hiányzik a data/history/snapshots.jsonl")
        return
    lines = [ln for ln in HISTORY_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    last = json.loads(lines[-1]) if lines else {}
    diff = []
    if last.get("date") != d.get("generated"):
        diff.append(f"dátum: snapshot {last.get('date')} vs dashboard {d.get('generated')}")
    for group in ("drivetrain_summary", "brand_summary"):
        snap = {r["key"]: r["score"] for r in last.get(group, [])}
        cur = {r["key"]: r["score"] for r in d.get(group, [])}
        if snap != cur:
            diff.append(f"{group}: snapshot {snap} vs dashboard {cur}")
    if last.get("factors") != {f["key"]: f["alap"] for f in d.get("factors", [])}:
        diff.append("a tényezők alap értékei eltérnek")
    c.add("history.snapshot", CRITICAL, not diff,
          "a legutóbbi history-snapshot = a mostani dashboard összesítői", diff)


VISIBLE_SKIP = re.compile(r"Path|path|style=|Number\(|^\s*//|^\s*\*")
INTERNAL_TEXT = re.compile(r"\.py\b|launchd|Claude|run_pipeline", re.IGNORECASE)


def check_template(c: Checks):
    lines = (DASHBOARD_DIR / "template.html").read_text(encoding="utf-8").splitlines()
    tofixed = [f"L{i}: {ln.strip()[:120]}" for i, ln in enumerate(lines, 1)
               if "toFixed(" in ln and not VISIBLE_SKIP.search(ln)]
    c.add("template.tofixed", WARN, not tofixed,
          "nincs toFixed() látható szövegben (számok csak fmt/fmtPlain/fmtInt-en át)", tofixed)
    internal = [f"L{i}: {ln.strip()[:120]}" for i, ln in enumerate(lines, 1)
                if INTERNAL_TEXT.search(ln) and not re.match(r"\s*(//|<!--|\*)", ln)]
    c.add("template.internal_text", WARN, not internal,
          "nincs belső karbantartási szöveg (scriptnév, launchd, Claude) a publikus oldalon", internal)


def run_post(c: Checks):
    d = check_dashboard(c)
    check_snapshot(c, d)
    check_template(c)


# ------------------------------------------------------------------- output

def worst(statuses) -> str:
    order = {"PASS": 0, "WARN": 1, "FAIL": 2}
    return max(statuses, key=lambda s: order[s], default="PASS")


def write_outputs(results: dict[str, Checks]):
    today = dt.date.today().isoformat()
    stored = load_json(VALIDATION_PATH) if VALIDATION_PATH.exists() else {}
    stages = stored.get("stages", {}) if stored.get("generated") == today else {}
    for stage, c in results.items():
        stages[stage] = {
            "status": c.status(),
            "run_at": dt.datetime.now().isoformat(timespec="seconds"),
            "checks": c.items,
        }
    out = {
        "generated": today,
        "status": worst(s["status"] for s in stages.values()),
        "stages": stages,
    }
    VALIDATION_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# Validációs riport ({today})", "",
          f"**Összesített állapot: {out['status']}**", "",
          "A modell előrejelzéseinek automatikus invariáns- és konzisztencia-ellenőrzése "
          "(`validate_forecast.py`). CRITICAL hiba esetén a pipeline nem commitol és nem push-ol.", ""]
    for stage in ("pre", "post"):
        if stage not in stages:
            continue
        s = stages[stage]
        md += [f"## Fázis: {stage} — {s['status']} ({s['run_at']})", "",
               "| | Súlyosság | Ellenőrzés | Leírás |", "|---|---|---|---|"]
        for ch in s["checks"]:
            mark = "✅" if ch["ok"] else ("❌" if ch["severity"] == CRITICAL else "⚠️")
            md.append(f"| {mark} | {ch['severity']} | `{ch['id']}` | {ch['message']} |")
        failed = [ch for ch in s["checks"] if not ch["ok"] and ch["details"]]
        if failed:
            md += ["", "### Részletek", ""]
            for ch in failed:
                md.append(f"**`{ch['id']}`**")
                md += [f"- {x}" for x in ch["details"][:20]]
                if len(ch["details"]) > 20:
                    md.append(f"- … és még {len(ch['details']) - 20}")
                md.append("")
        md.append("")
    REPORTS_DIR.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(md), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--stage", choices=("pre", "post", "all"), default="all")
    args = ap.parse_args()

    stages = ("pre", "post") if args.stage == "all" else (args.stage,)
    results = {}
    for stage in stages:
        c = Checks(stage)
        try:
            run_pre(c) if stage == "pre" else run_post(c)
        except Exception as e:  # egy összeomló ellenőrzés maga is kritikus hiba
            c.add(f"{stage}.crash", CRITICAL, False, f"az ellenőrzés hibával leállt: {type(e).__name__}: {e}")
        results[stage] = c

    out = write_outputs(results)
    for stage, c in results.items():
        print(f"Validáció [{stage}]: {c.status()}")
        for ch in c.items:
            if not ch["ok"]:
                print(f"  {ch['severity']:8} {ch['id']}: {ch['message']}")
                for x in ch["details"][:5]:
                    print(f"           - {x}")
    print(f"Riport: {REPORT_PATH.relative_to(ROOT)}  (összesített: {out['status']})")

    if any(c.status() == "FAIL" for c in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
