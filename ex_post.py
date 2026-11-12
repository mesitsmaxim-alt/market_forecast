"""Ex-post visszamérés: amit a dashboard korábban előre jelzett, azt most a
tényleges adattal vetjük össze.

- archive_forecasts(): minden dashboard-build a publikált vetítő kártyák pontjait
  és sávjait a data/history/forecasts.jsonl-be írja (célidőszakkal együtt).
- evaluate(): a jelenlegi data/*.json alapján megnézi, melyik célidőszak adata
  jelent meg azóta, és összeveti a vetítéssel és a naiv becsléssel ("marad, ami
  volt"). A hajtás-irányokat (snapshots.jsonl) az Eurostat új autós részesedésével
  veti össze, amint a célév adata megvan.
- python3 ex_post.py --backfill: a korábbi futások vetítéseit a git-történetből
  (dashboard/dashboard_data.json) tölti vissza. Egyszer kellett, idempotens.

A kamatkártya ("következő kamatdöntés") eseményalapú, nem időszakos, ezért kimarad.
"""

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
ARCHIVE_PATH = DATA_DIR / "history" / "forecasts.jsonl"
SNAPSHOTS_PATH = DATA_DIR / "history" / "snapshots.jsonl"
OUT_PATH = DATA_DIR / "ex_post.json"

HU_MONTHS = ["január", "február", "március", "április", "május", "június", "július",
             "augusztus", "szeptember", "október", "november", "december"]
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
NEUTRAL_PTS = 5  # a dashboard semleges sávja (engine.classify ±0,05)


# ---------- időszak-címkék egységesítése (egész index) ----------
def month_idx(label: str) -> int:
    label = str(label)
    if "." in label:  # "2026. október"
        y, m = label.split(".", 1)
        return int(y) * 12 + HU_MONTHS.index(m.strip())
    y, m = label.split("-")  # "2026-10"
    return int(y) * 12 + int(m) - 1


def quarter_idx(label: str) -> int:
    label = str(label)
    if "Q" in label:  # "2026 Q2"
        y, q = label.split("Q")
        return int(y) * 4 + int(q) - 1
    y, rest = label.split(".", 1)  # "2026. II. negyedév"
    return int(y) * 4 + ROMAN[rest.strip().split(".")[0]] - 1


def idx_label(freq: str, i: int) -> str:
    if freq == "M":
        return f"{i // 12}. {HU_MONTHS[i % 12]}"
    if freq == "Q":
        return f"{i // 4}. {['I', 'II', 'III', 'IV'][i % 4]}. negyedév"
    return f"{i}"


# ---------- kártyák: hol a vetítés a dashboard-adatban, és honnan a tény ----------
def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _series(labels, values, to_idx) -> dict[int, float]:
    return {to_idx(l): v for l, v in zip(labels, values) if v is not None}


def _actual_forgalomba():
    d = _load("forgalomba.json")
    return _series(d["quarters"], d["total"], quarter_idx)


def _actual_toltoinfra():
    d = _load("toltoinfra.json")["quarterly_counts"]
    return _series(d["quarters"], [a + b for a, b in zip(d["ac"], d["dc"])], quarter_idx)


def _actual_szentiment(key):
    d = _load("szentiment.json")
    return _series(d["months"], d[key], month_idx)


def _actual_eurhuf():
    d = _load("makro.json")["eur_huf_havi"]
    return _series(d["months"], d["values"], month_idx)


def _actual_fuel_share(fuel):
    d = _load("jarmuallomany.json")
    return _series(d["years"], [f / t * 100 for f, t in zip(d["fuel_types"][fuel], d["total"])], int)


def _actual_realjovedelem(key):
    d = _load("realjovedelem.json")
    return _series(d["years"], d[key], int)


# id: (felirat, egység, gyakoriság, vetítés kinyerése real-ből, (bázis-címke, bázis-érték) real-ből, tény-sor)
CARDS = {
    "forgalomba": ("Első forgalomba helyezések (negyedév)", "db", "Q",
                   lambda r: r["forgalomba"]["forecast"],
                   lambda r: (quarter_idx(r["forgalomba"]["last_quarter"]), r["forgalomba"]["total_last"]),
                   _actual_forgalomba),
    "toltoinfra": ("Nyilvános töltőpontok", "db", "Q",
                   lambda r: r["toltoinfra"]["forecast"],
                   lambda r: (quarter_idx(r["toltoinfra"]["last_quarter"]), r["toltoinfra"]["ac_last"] + r["toltoinfra"]["dc_last"]),
                   _actual_toltoinfra),
    "vasarlasi_szandek": ("Vásárlási szándék", "pont", "M",
                          lambda r: r["szentiment"]["mp_forecast"],
                          lambda r: (month_idx(r["szentiment"]["last_month"]), r["szentiment"]["mp_last"]),
                          lambda: _actual_szentiment("major_purchases_intention")),
    "fogyasztoi_bizalom": ("Fogyasztói bizalom", "pont", "M",
                           lambda r: r["szentiment"]["cc_forecast"],
                           lambda r: (month_idx(r["szentiment"]["last_month"]), r["szentiment"]["cc_last"]),
                           lambda: _actual_szentiment("consumer_confidence")),
    "eurhuf": ("Euró/forint árfolyam", "Ft", "M",
               lambda r: r["makro"]["eurhuf_forecast"],
               lambda r: (month_idx(r["makro"]["eurhuf_month"]), r["makro"]["eurhuf_last"]),
               _actual_eurhuf),
    **{f"allomany_{fuel}": (f"{name} részesedése az állományban", "%", "Y",
                            (lambda fuel: lambda r: r["jarmuallomany"]["fuel_share_forecast"][fuel])(fuel),
                            (lambda fuel: lambda r: (int(r["jarmuallomany"]["last_year"]),
                                                     r["jarmuallomany"]["fuel_shares_series"][fuel][-1]))(fuel),
                            (lambda fuel: lambda: _actual_fuel_share(fuel))(fuel))
       for fuel, name in (("benzin", "Benzin"), ("dizel", "Dízel"), ("hibrid", "Hibrid"), ("elektromos", "Elektromos"))},
    "realkereset": ("Reálkereset változása", "%", "Y",
                    lambda r: r["realjovedelem"]["wage_forecast"],
                    lambda r: (int(r["realjovedelem"]["years_full"][-1]), r["realjovedelem"]["wage_series_full"][-1]),
                    lambda: _actual_realjovedelem("real_wage_yoy_pct")),
    "realjovedelem": ("Reáljövedelem változása", "%", "Y",
                      lambda r: r["realjovedelem"]["income_forecast"],
                      lambda r: (int(r["realjovedelem"]["years_full"][-1]), r["realjovedelem"]["income_series_full"][-1]),
                      lambda: _actual_realjovedelem("real_income_yoy_pct")),
}


def extract_forecasts(combined: dict) -> list[dict]:
    """A dashboard-adatból a vetítő kártyák archiválható rekordjai. A régebbi
    futásokból hiányzó kártyákat csendben kihagyja."""
    out = []
    for cid, (_, _, freq, get_fc, get_base, _) in CARDS.items():
        try:
            fc = get_fc(combined["real"])
            base, base_value = get_base(combined["real"])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if not fc or not fc.get("points"):
            continue
        out.append({"made": combined["generated"], "card": cid, "freq": freq, "base": base,
                    "base_value": base_value, "points": fc["points"],
                    "lower": fc.get("lower"), "upper": fc.get("upper"),
                    "kind": fc.get("kind", "linear")})
    return out


def _read_archive() -> list[dict]:
    if not ARCHIVE_PATH.exists():
        return []
    return [json.loads(l) for l in ARCHIVE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def archive_forecasts(combined: dict) -> None:
    """A mai vetítések hozzáfűzése; egy napon belüli újrafuttatás felülírja a
    nap korábbi rekordjait (mint a snapshotoknál)."""
    keep = [r for r in _read_archive() if r["made"] != combined["generated"]]
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = keep + extract_forecasts(combined)
    rows.sort(key=lambda r: (r["made"], r["card"]))
    ARCHIVE_PATH.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def backfill_from_git() -> int:
    """A korábbi futások vetítései a dashboard_data.json git-történetéből."""
    commits = subprocess.run(["git", "log", "--format=%h", "--", "dashboard/dashboard_data.json"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    by_day: dict[str, dict] = {}
    for c in reversed(commits):  # régebbitől az újabbig: a nap utolsó commitja nyer
        raw = subprocess.run(["git", "show", f"{c}:dashboard/dashboard_data.json"],
                             cwd=ROOT, capture_output=True, text=True).stdout
        try:
            combined = json.loads(raw)
        except json.JSONDecodeError:
            continue
        by_day[combined["generated"]] = combined
    existing = {r["made"] for r in _read_archive()}
    added = []
    for day, combined in by_day.items():
        if day not in existing:
            added += extract_forecasts(combined)
    if added:
        rows = _read_archive() + added
        rows.sort(key=lambda r: (r["made"], r["card"]))
        ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVE_PATH.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return len(added)


# ---------- értékelés ----------
def _direction_check(today: str) -> dict:
    """Hajtás-irányok: a futás idején legfrissebb Eurostat-év utáni év új autós
    részesedés-változása vs. a modell előjele (csak a ±5 ponton kívüli hívások)."""
    uj = _load("uj_hajtas.json")
    years = uj["years"]
    shares = uj["shares_pct"]
    snaps = []
    if SNAPSHOTS_PATH.exists():
        by_date = {}
        for line in SNAPSHOTS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                s = json.loads(line)
                by_date[s["date"]] = s
        snaps = list(by_date.values())
    # célév: a futás naptári éve (a futáskor még nincs róla éves Eurostat-adat,
    # és a 12 hónapos horizont nagy része erre és a következő évre esik)
    calls, pending_years = [], set()
    for s in snaps:
        target = int(s["date"][:4])
        if target in years and target - 1 in years:
            for r in s.get("drivetrain_summary", []):
                pts = r["score"] * 100
                if abs(pts) < NEUTRAL_PTS:
                    continue
                i, j = years.index(target - 1), years.index(target)
                change = shares[r["key"]][j] - shares[r["key"]][i]
                calls.append({"made": s["date"], "key": r["key"], "target_year": target,
                              "score": round(pts, 1), "share_change_pp": round(change, 2),
                              "hit": (pts > 0) == (change > 0)})
        else:
            pending_years.add(target)
    return {"resolved": calls, "pending_years": sorted(pending_years),
            "last_data_year": years[-1], "n_snapshots": len(snaps)}


def evaluate(today: str | None = None) -> dict:
    today = today or dt.date.today().isoformat()
    rows = _read_archive()
    # (kártya, bázis) szerint a legutolsó publikált vetítés számít: az állt
    # legtovább a dashboardon, mielőtt új adat jött volna
    latest: dict[tuple, dict] = {}
    for r in rows:
        k = (r["card"], r["base"])
        if k not in latest or r["made"] >= latest[k]["made"]:
            latest[k] = r
    actual_cache = {cid: spec[5]() for cid, spec in CARDS.items()}
    # a kártya mostani típusa (a legutóbbi futásé): a régi lineáris vetítés helyén ma már naiv állhat
    now_kind = {r["card"]: r.get("kind", "linear") for r in sorted(rows, key=lambda r: r["made"])}
    resolved, pending = [], []
    for (cid, base), r in sorted(latest.items(), key=lambda kv: (kv[1]["made"], kv[0][0])):
        label, unit, freq = CARDS[cid][:3]
        act = actual_cache[cid]
        for step, point in enumerate(r["points"], start=1):
            target = base + step
            lo = r["lower"][step - 1] if r.get("lower") else None
            hi = r["upper"][step - 1] if r.get("upper") else None
            item = {"card": cid, "label": label, "unit": unit, "made": r["made"],
                    "target": idx_label(freq, target), "step": step, "point": round(point, 3),
                    "lower": None if lo is None else round(lo, 3), "upper": None if hi is None else round(hi, 3),
                    "naive_card": r.get("kind") == "naive",
                    "now_naive": now_kind.get(cid) == "naive"}
            if target in act:
                a = act[target]
                item.update({"actual": a, "error": round(a - point, 3),
                             "naive_error": round(a - r["base_value"], 3),
                             "in_band": None if lo is None else (lo <= a <= hi)})
                resolved.append(item)
            else:
                pending.append({**item, "_idx": target})
    banded = [x for x in resolved if x["in_band"] is not None]
    linear = [x for x in resolved if not x["naive_card"]]
    summary = {
        "n_resolved": len(resolved), "n_pending": len(pending),
        "coverage": round(sum(x["in_band"] for x in banded) / len(banded), 3) if banded else None,
        "n_banded": len(banded),
        # a naiv kártyák pontja maga a naiv becslés, ezért az összevetés csak a lineáris kártyákon értelmes
        "n_linear": len(linear),
        "linear_beats_naive": sum(abs(x["error"]) < abs(x["naive_error"]) for x in linear),
    }
    # kártyánként a legkorábbi még nyitott célidőszak (pending már időrendben van)
    next_by_card: dict[str, str] = {}
    for p in sorted(pending, key=lambda x: (x["card"], x["_idx"])):
        next_by_card.setdefault(p["label"], p["target"])
    for p in pending:
        p.pop("_idx")
    summary["next_by_card"] = next_by_card
    return {"generated": today, "summary": summary, "resolved": resolved[-40:],
            "pending_count_by_card": {cid: sum(1 for p in pending if p["card"] == cid) for cid in CARDS},
            "directions": _direction_check(today)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="korábbi futások vetítései a git-történetből")
    args = ap.parse_args()
    if args.backfill:
        print(f"Visszatöltve: {backfill_from_git()} vetítés-rekord")
    res = evaluate()
    OUT_PATH.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    s = res["summary"]
    print(f"Ex-post: {s['n_resolved']} lezárt, {s['n_pending']} függő célidőszak; "
          f"sávlefedettség {s['coverage']}; lineáris jobb a naivnál {s['linear_beats_naive']}/{s['n_linear']}")


if __name__ == "__main__":
    main()
