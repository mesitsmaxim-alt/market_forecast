#!/usr/bin/env python3
"""
Összeállítja a dashboard adatcsomagját (dashboard_data.json) a friss
forgatókönyv-számításból és a valós adatforrásokból, majd beleégeti a
dashboard/template.html sablonba -> dashboard/dashboard.html.

Ez a script NEM publikál semmit (az Artifact-publikálás csak egy aktív
Claude Code munkamenetből lehetséges) - csak előkészíti a friss,
publikálásra kész HTML-t. A publikáláshoz kérd meg Claude-ot: "frissítsd
a dashboardot" egy soron következő munkamenetben, és a dashboard/dashboard.html
tartalmát fogja újrapublikálni a meglévő linkre.

Használat:
    python3 dashboard/build_dashboard.py
Kimenet:
    dashboard/dashboard_data.json
    dashboard/dashboard.html
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import (  # noqa: E402
    compute_segments, classify, load_config, SCENARIOS,
    MOMENTUM_WEIGHT, MOMENTUM_WINDOW_YEARS, REG_MOMENTUM_WEIGHT,
)
from forecast import forecast_card  # noqa: E402

DATA_DIR = ROOT / "data"
HISTORY_PATH = DATA_DIR / "history" / "snapshots.jsonl"
DASHBOARD_DIR = Path(__file__).parent
TEMPLATE_PATH = DASHBOARD_DIR / "template.html"
DATA_OUT_PATH = DASHBOARD_DIR / "dashboard_data.json"
HTML_OUT_PATH = DASHBOARD_DIR / "dashboard.html"
HISTORY_LIMIT = 60

CALIBRATED_FACTORS = {
    "oil_price", "charging_infra", "financing_cost",
    "consumer_sentiment", "purchasing_power",
}
# Kézi, forrásmegjelölt adatfájlból kalibrált tényezők (nincs gépi forrásuk,
# ld. calibrate_factors.py) — a dashboard külön "kézi forrás" jelzést ad nekik.
MANUAL_SOURCE_FACTORS = {"battery_cost", "ev_tariffs", "co2_regulation"}

# A dashboard "Hogyan számol a modell?" blokkjához: tényezőnként a forrás
# rövid, látogatóknak szóló neve és a hatókör (hazai adat vagy a magyar piacra
# ható EU-s / globális tényező). Új tényezőnél ide is fel kell venni.
FACTOR_SOURCES = {
    "oil_price": ("holtankoljak.hu — hazai kútárak", "HU"),
    "battery_cost": ("BloombergNEF — éves akkumulátorár-felmérés", "EU/globális"),
    "charging_infra": ("EAFO — magyarországi nyilvános töltőpontok", "HU"),
    "ev_tariffs": ("Európai Bizottság — vámok kínai elektromos autókra", "EU/globális"),
    "co2_regulation": ("EU flotta-CO2 rendelet (2019/631)", "EU/globális"),
    "financing_cost": ("Magyar Nemzeti Bank — alapkamat", "HU"),
    "consumer_sentiment": ("Eurostat — magyar fogyasztói felmérés", "HU"),
    "purchasing_power": ("KSH — reálkereset, reáljövedelem", "HU"),
}
EXAMPLE_SEGMENT = ("BEV", "tomeggyarto", "uj")  # a módszertani példa szegmense

# Az automatikusan (minden pipeline-futáskor) frissülő adatforrások - a run_pipeline.sh
# fetchereivel összhangban. Ebből számolja a dashboard és a digest a forrásszámot
# (korábban beégetett "6" volt). Új automata fetchernél ide is fel kell venni.
AUTOMATED_SOURCES = [
    "KSH személygépkocsi-állomány (sza0025)",
    "KSH forgalomba helyezés márkánként (sza0070)",
    "KSH reáljövedelem / reálkereset (gdp0035)",
    "KSH régiós üzemanyagárak",
    "MNB alapkamat és EUR/HUF",
    "holtankoljak.hu élő kútárak",
    "Eurostat fogyasztói felmérés (ei_bsco_m)",
    "Eurostat új autók hajtás szerint (road_eqr_carpda)",
    "Eurostat HICP üzemanyag-árindex (prc_hicp_minr)",
]


def load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def driver_label(label: str) -> str:
    """Az engine momentum-címkéiben szegmensenként más szám van; a csoport-
    átlagoláshoz egységes, látogatóknak szóló címke kell."""
    if label.startswith("Megfigyelt piaci momentum (új autók részesedése"):
        return "Valós piaci lendület (új autók részesedése)"
    if label.startswith("Megfigyelt piaci momentum (KSH állomány"):
        return "Valós piaci lendület (KSH-állomány)"
    if label.startswith("Megfigyelt piaci momentum (forgalomba helyezés"):
        return "Valós piaci lendület (forgalomba helyezés)"
    return label


DRIVETRAINS = ("ICE", "HEV", "PHEV", "BEV")
# Évjárat-sávonként milyen piaci összetétellel súlyozzuk a hajtásokat:
#   ("new", a, b) = azoknak az éveknek az ÚJ eladásai (Eurostat), amikor a sáv
#                   autói újként forgalomba kerültek (mai év - b ... mai év - a);
#                   a=b=0: a legutóbbi elérhető év
#   ("stock",)    = a mostani KSH-állomány
# A segments.json-ban ismeretlen sáv a "stock"-ot kapja.
YEAR_BUCKET_MARKET = {
    "uj": ("new", 0, 0),
    "fiatal_hasznalt": ("new", 3, 5),
    "idosebb_hasznalt": ("stock",),
}


def _normalize(raw: dict) -> dict:
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()} if total else {}


def stock_market_weights(phev_ratio: float = 0.5) -> dict:
    """Hajtás-arányok a KSH-állományból (benzin+dízel -> ICE, elektromos ->
    BEV, az "egyéb" kimarad). A KSH a hibridet nem bontja HEV/PHEV-re: a
    `phev_ratio` arányban osztjuk el (Eurostat-adat híján fele-fele)."""
    fuel = load_json("jarmuallomany.json")["fuel_types"]
    last = {k: v[-1] for k, v in fuel.items()}
    hyb = last.get("hibrid", 0)
    return _normalize({
        "ICE": last.get("benzin", 0) + last.get("dizel", 0),
        "HEV": hyb * (1 - phev_ratio),
        "PHEV": hyb * phev_ratio,
        "BEV": last.get("elektromos", 0),
    })


def drivetrain_market_weights(year_buckets: dict) -> dict:
    """Piaci súlyok évjárat-sávonként: {"weights": {sáv: {hajtás: arány}},
    "basis": {sáv: leírás}}. Az új és a fiatal használt sávot az Eurostat új-
    eladási arányai (data/uj_hajtas.json), az idősebbet a KSH-állomány adja.
    Közelítés: a hazai használt piacon sok a külföldről behozott autó, amelyek
    összetétele eltérhet a hazai újautó-eladásokétól."""
    path = DATA_DIR / "uj_hajtas.json"
    if not path.exists():
        w = stock_market_weights()
        return {"weights": {yb: w for yb in year_buckets},
                "basis": {yb: "a mostani autóállomány" for yb in year_buckets}}

    uh = json.loads(path.read_text(encoding="utf-8"))
    years, shares = uh["years"], uh["shares_pct"]
    # a régebbi állomány hibrid-felosztásához a legkorábbi elérhető év aránya
    first_hyb = shares["HEV"][0] + shares["PHEV"][0]
    phev_ratio = shares["PHEV"][0] / first_hyb if first_hyb else 0.5
    this_year = dt.date.today().year

    weights, basis = {}, {}
    for yb in year_buckets:
        spec = YEAR_BUCKET_MARKET.get(yb, ("stock",))
        if spec[0] == "new":
            if spec[1] == 0:
                sel = [years[-1]]
            else:
                sel = [y for y in years if this_year - spec[2] <= y <= this_year - spec[1]] or [years[0]]
            idx = [years.index(y) for y in sel]
            weights[yb] = _normalize({d: sum(shares[d][i] for i in idx) / len(idx) for d in DRIVETRAINS})
            span = f"{sel[0]}" if len(sel) == 1 else f"{sel[0]}–{sel[-1]}"
            basis[yb] = f"a {span}. évi új eladások"
        else:
            weights[yb] = stock_market_weights(phev_ratio)
            basis[yb] = "a mostani autóállomány"
    return {"weights": weights, "basis": basis}


def build_engine_summary() -> dict:
    results, factors = compute_segments()
    mkt = drivetrain_market_weights(load_config()[1]["year_buckets"])
    mkt_w = mkt["weights"]
    _, seg_config = load_config()
    yb_weight = {k: v["weight"] for k, v in seg_config["year_buckets"].items()}

    def agg(key_fn, label_fn):
        from collections import defaultdict
        buckets = defaultdict(lambda: {"pesszimista": [], "alap": [], "optimista": []})
        # tényezőnkénti hozzájárulás (pontban, évjárat-súllyal - ugyanúgy, ahogy a
        # pontszámba kerül), csoportonként átlagolva: ebből írja a dashboard a
        # kártyák konklúzióját ("mi hajtja")
        contrib = defaultdict(lambda: {s: defaultdict(float) for s in SCENARIOS})
        counts = defaultdict(int)
        # piacsúlyozott átlag: a hajtástípusokat a valós állomány-arányuk szerint
        # súlyozzuk (évjárat-sávonként más összetétel), nem egyformán
        # (ld. drivetrain_market_weights)
        mw_sum = defaultdict(lambda: defaultdict(float))
        mw_den = defaultdict(float)
        for r in results:
            b = buckets[key_fn(r)]
            counts[key_fn(r)] += 1
            w = mkt_w.get(r.year_bucket, {}).get(r.drivetrain, 0)
            mw_den[key_fn(r)] += w
            for scenario in SCENARIOS:
                mw_sum[key_fn(r)][scenario] += r.scores[scenario] * w
            for scenario in SCENARIOS:
                b[scenario].append(r.scores[scenario])
                for lbl, c in r.drivers[scenario]:
                    contrib[key_fn(r)][scenario][driver_label(lbl)] += c * yb_weight[r.year_bucket] * 100
        out = []
        for k, scenario_scores in buckets.items():
            avg = {s: sum(vals) / len(vals) for s, vals in scenario_scores.items()}
            out.append({
                "key": k, "label": label_fn(k),
                "score": round(avg["alap"], 4), "dir": classify(avg["alap"]),
                "pesszimista": round(avg["pesszimista"], 4),
                "optimista": round(avg["optimista"], 4),
                "dirs": {s: classify(avg[s]) for s in SCENARIOS},
                "market_weighted": ({s: round(mw_sum[k][s] / mw_den[k], 4) for s in SCENARIOS}
                                    if mw_den[k] else None),
                "drivers": {s: sorted(
                    ({"label": lbl, "points": round(v / counts[k], 2)} for lbl, v in contrib[k][s].items()),
                    key=lambda x: -abs(x["points"]),
                ) for s in SCENARIOS},
            })
        out.sort(key=lambda x: -x["score"])
        return out

    drivetrain_summary = agg(
        lambda r: r.drivetrain,
        lambda k: next(r.drivetrain_label for r in results if r.drivetrain == k),
    )
    brand_summary = agg(
        lambda r: r.brand_tier,
        lambda k: next(r.brand_tier_label for r in results if r.brand_tier == k),
    )
    year_summary = agg(
        lambda r: r.year_bucket,
        lambda k: next(r.year_bucket_label for r in results if r.year_bucket == k),
    )

    results_sorted = sorted(results, key=lambda r: r.scores["alap"], reverse=True)

    def segment_row(r):
        return {
            "label": f"{r.drivetrain_label} / {r.brand_tier_label} / {r.year_bucket_label}",
            "score": round(r.scores["alap"], 4),
            "dir": classify(r.scores["alap"]),
        }

    # Mind a 48 szegmens mindhárom forgatókönyvre - a dashboard forgatókönyv-
    # váltója és hőtérképe ebből számol kliensoldalon (a top_winners/
    # top_losers az alap forgatókönyvre marad a digest számára).
    segments = [{
        "drivetrain": r.drivetrain, "drivetrain_label": r.drivetrain_label,
        "brand_tier": r.brand_tier, "brand_tier_label": r.brand_tier_label,
        "year_bucket": r.year_bucket, "year_bucket_label": r.year_bucket_label,
        "scores": {s: round(r.scores[s], 4) for s in SCENARIOS},
        "dirs": {s: classify(r.scores[s]) for s in SCENARIOS},
        # a hőtérkép kattintásos bontásához: tényezőnkénti hozzájárulás pontban,
        # évjárat-súllyal (összegük = a szegmens pontszáma)
        "drivers": {s: [{"label": driver_label(lbl),
                         "points": round(c * yb_weight[r.year_bucket] * 100, 2)}
                        for lbl, c in r.drivers[s]] for s in SCENARIOS},
    } for r in results]

    top_winners = [segment_row(r) for r in results_sorted[:5]]
    top_losers = [segment_row(r) for r in results_sorted[-5:][::-1]]

    factors_out = []
    for key, f in factors.items():
        factors_out.append({
            "key": key,
            "label": f["label"],
            "unit": f["unit"],
            "calibrated": ("auto" if key in CALIBRATED_FACTORS
                           else "manual" if key in MANUAL_SOURCE_FACTORS else False),
            "pesszimista": f["scenarios"]["pesszimista"],
            "alap": f["scenarios"]["alap"],
            "optimista": f["scenarios"]["optimista"],
        })

    return {
        "factors": factors_out,
        "drivetrain_summary": drivetrain_summary,
        "brand_summary": brand_summary,
        "year_summary": year_summary,
        "top_winners": top_winners,
        "top_losers": top_losers,
        "segments": segments,
        "market_weights": {
            "weights": {yb: {d: round(v, 4) for d, v in w.items()} for yb, w in mkt_w.items()},
            "basis": mkt["basis"],
            "labels": {k: v["label"] for k, v in load_config()[1]["year_buckets"].items()},
        },
    }


def build_methodology(factors_out: list[dict]) -> dict:
    """A "Hogyan számol a modell?" blokk adatai - minden szám a kódból / az
    adatokból jön, hogy a magyarázat ne avuljon el a modell változásakor."""
    _, segments = load_config()
    results, _ = compute_segments()

    ex = next((r for r in results
               if (r.drivetrain, r.brand_tier, r.year_bucket) == EXAMPLE_SEGMENT), None)
    example = None
    if ex is not None:
        weight = segments["year_buckets"][ex.year_bucket]["weight"]
        example = {
            "label": f"{ex.drivetrain_label} / {ex.brand_tier_label.split(' (')[0]} / {ex.year_bucket_label}",
            "score": round(ex.scores["alap"] * 100, 1),
            # az engine driver-címkéiben tizedespont van (pl. "+42.5%/év") -> vessző
            "top": [{"label": re.sub(r"(\d)\.(\d)", r"\1,\2", lbl).replace("Megfigyelt piaci momentum", "Valós piaci lendület").replace(" pp/év", " százalékpont/év"),
                     "points": round(c * weight * 100, 1)}
                    for lbl, c in ex.drivers["alap"][:3]],
        }

    backtest = None
    bt_path = DATA_DIR / "backtest.json"
    if bt_path.exists():
        bt = json.loads(bt_path.read_text(encoding="utf-8"))
        labels = {f["key"]: f["label"] for f in factors_out}
        backtest = {
            "comparisons": bt["comparisons"],
            "tested_factors": [labels.get(k, k) for k in bt["tested_factors"]],
        }

    return {
        "factors": [{
            "label": f["label"], "unit": f["unit"], "alap": f["alap"],
            "source": FACTOR_SOURCES.get(f["key"], ("—", "—"))[0],
            "scope": FACTOR_SOURCES.get(f["key"], ("—", "—"))[1],
        } for f in factors_out],
        "n_segments": len(results),
        "dimensions": {
            "drivetrains": [d["label"] for d in segments["drivetrains"].values()],
            "brand_tiers": [b["label"].split(" (")[0] for b in segments["brand_tiers"].values()],
            "year_buckets": [{"label": y["label"], "weight": y["weight"]}
                             for y in segments["year_buckets"].values()],
        },
        "momentum": {
            "stock_weight": MOMENTUM_WEIGHT, "stock_window_years": MOMENTUM_WINDOW_YEARS,
            "reg_weight": REG_MOMENTUM_WEIGHT,
            # melyik forrásból jön a hajtás-momentum (Eurostat új autók vagy tartalék KSH-állomány)
            "drivetrain_source": "share_pp" if (DATA_DIR / "uj_hajtas.json").exists() else "stock_cagr",
        },
        "example": example,
        "backtest": backtest,
    }


def cagr(series: list[float], window: int) -> float:
    w = min(window, len(series) - 1)
    s, e = series[-1 - w], series[-1]
    if s <= 0:
        return 0.0
    return ((e / s) ** (1 / w) - 1) * 100


BRAND_MOVER_MIN_UNITS = 1000  # ennél kisebb éves volumenű márka kimarad (kis bázison a % zajos)
BRAND_MOVER_N = 6


def build_brand_movers(f: dict) -> dict | None:
    """Leggyorsabban növő / csökkenő márkák a KSH első forgalomba helyezési
    adatából (új + használt import!): a legutóbbi 4 negyedév összege vs. az
    azt megelőző 4 negyedévé - egyetlen negyedév helyett, mert az zajos."""
    quarters, brands = f["quarters"], f["brands"]
    if len(quarters) < 8:
        return None
    rows = []
    total_now = sum(f["total"][-4:])
    total_prev = sum(f["total"][-8:-4])
    for name, series in brands.items():
        now, prev = sum(series[-4:]), sum(series[-8:-4])
        if now < BRAND_MOVER_MIN_UNITS or prev <= 0:
            continue
        rows.append({
            "brand": name, "units": now, "prev_units": prev,
            "change_pct": round((now / prev - 1) * 100, 1),
            "share_pct": round(now / total_now * 100, 2),
            "share_pp_change": round((now / total_now - prev / total_prev) * 100, 2),
        })
    rows.sort(key=lambda r: -r["change_pct"])
    return {
        "window_now": f"{quarters[-4]} – {quarters[-1]}",
        "window_prev": f"{quarters[-8]} – {quarters[-5]}",
        "market_change_pct": round((total_now / total_prev - 1) * 100, 1),
        "min_units": BRAND_MOVER_MIN_UNITS,
        "n_brands": len(rows),
        "growing": rows[:BRAND_MOVER_N],
        "declining": rows[::-1][:BRAND_MOVER_N],
    }


def build_real_snapshot() -> dict:
    out = {}

    j = load_json("jarmuallomany.json")
    total = j["total"]
    fuel = j["fuel_types"]
    out["jarmuallomany"] = {
        "last_year": j["years"][-1],
        "total_last": total[-1],
        "total_yoy": (total[-1] / total[-2] - 1) * 100,
        "fuel_shares": {k: round(v[-1] / total[-1] * 100, 1) for k, v in fuel.items()},
        "fuel_cagr5": {k: round(cagr(v, 5), 1) for k, v in fuel.items()},
        # teljes évsor a Történet fülhöz + hajtástípus-részesedés előrejelzéshez
        "years_full": j["years"],
        "fuel_shares_series": {
            k: [round(v[i] / total[i] * 100, 2) for i in range(len(total))]
            for k, v in fuel.items()
        },
        "fuel_share_forecast": {
            k: forecast_card(
                [round(v[i] / total[i] * 100, 2) for i in range(len(total))],
                steps=2, horizon_label="2 év múlva (becsült, az utolsó 6 év trendje alapján)",
                window=6,
            )
            for k, v in fuel.items()
        },
    }

    # Élő üzemanyagár (holtankoljak.hu) - mindig a jelenlegi árat mutatja,
    # nem a befagyott KSH-kiadvány pillanatképét.
    ue = load_json("uzemanyagar_elo.json")
    # a forrás középső oszlopa nem megbízhatóan "1 hónappal korábbi" (ld.
    # fuel_report.py) - csak az 1 évvel korábbi és a mostani érték kerül át
    current, _middle, year_ago = ue["periods"]
    benzin_row = ue["fuels"]["95-ös Benzin E10"]
    dizel_row = ue["fuels"]["Gázolaj"]
    out["uzemanyagar"] = {
        "last_week": ue["headline_date"],
        "benzin_last": ue["headline"]["benzin_95"],
        "dizel_last": ue["headline"]["gazolaj"],
        "benzin_series": [benzin_row[year_ago], benzin_row[current]],
        "dizel_series": [dizel_row[year_ago], dizel_row[current]],
        "year_ago_period": year_ago,
    }

    m = load_json("makro.json")
    out["makro"] = {
        "alapkamat_last": m["alapkamat"]["values"][-1],
        "alapkamat_date": m["alapkamat"]["dates"][-1],
        "alapkamat_series": m["alapkamat"]["values"][-10:],
        "alapkamat_series_full": m["alapkamat"]["values"],
        "alapkamat_forecast": forecast_card(m["alapkamat"]["values"], steps=1, horizon_label="következő kamatdöntés (irányjelzés, az utolsó 8 döntés trendje alapján)", window=8),
        "eurhuf_last": m["eur_huf_havi"]["values"][-1],
        "eurhuf_month": m["eur_huf_havi"]["months"][-1],
        "eurhuf_series": m["eur_huf_havi"]["values"][-24:],
        "eurhuf_series_full": m["eur_huf_havi"]["values"],
        "eurhuf_forecast": forecast_card(m["eur_huf_havi"]["values"], steps=6, horizon_label="6 hónap múlva (becsült, az utolsó 24 hónap trendje alapján)", window=24),
    }

    t = load_json("toltoinfra.json")
    qc = t["quarterly_counts"]
    total_toltoinfra = [a + d for a, d in zip(qc["ac"], qc["dc"])]
    out["toltoinfra"] = {
        "last_quarter": qc["quarters"][-1],
        "ac_last": qc["ac"][-1],
        "dc_last": qc["dc"][-1],
        "total_series": total_toltoinfra[-12:],
        "ac_series": qc["ac"][-12:],
        "dc_series": qc["dc"][-12:],
        "total_series_full": total_toltoinfra,
        "forecast": forecast_card(total_toltoinfra, steps=4, horizon_label="4 negyedév múlva (becsült, az utolsó 8 negyedév trendje alapján)", window=8),
    }

    f = load_json("forgalomba.json")
    out["forgalomba"] = {
        "last_quarter": f["quarters"][-1],
        "total_last": f["total"][-1],
        "total_series": f["total"][-8:],
        "total_series_full": f["total"],
        "total_yoy": (f["total"][-1] / f["total"][-5] - 1) * 100 if len(f["total"]) >= 5 else None,
        "forecast": forecast_card(f["total"], steps=4, horizon_label="4 negyedév múlva (becsült, az utolsó 8 negyedév trendje alapján)", window=8),
        "brand_movers": build_brand_movers(f),
    }

    if (DATA_DIR / "uj_hajtas.json").exists():
        uh = load_json("uj_hajtas.json")
        out["uj_hajtas"] = {
            "source": uh["source"],
            "years": uh["years"],
            "shares": uh["detail_shares_pct"],          # benzin / dizel / hibrid / elektromos / egyeb
            "phev_share": uh["shares_pct"]["PHEV"],     # a hibridből a plug-in rész
            "totals": uh["counts"]["total"],
        }

    s = load_json("szentiment.json")
    out["szentiment"] = {
        "last_month": s["months"][-1],
        "mp_last": s["major_purchases_intention"][-1],
        "mp_series": s["major_purchases_intention"][-24:],
        "mp_series_full": s["major_purchases_intention"],
        "mp_forecast": forecast_card(s["major_purchases_intention"], steps=6, horizon_label="6 hónap múlva (becsült, az utolsó 36 hónap trendje alapján)", window=36),
        "cc_last": s["consumer_confidence"][-1],
        "cc_series": s["consumer_confidence"][-24:],
        "cc_series_full": s["consumer_confidence"],
        "cc_forecast": forecast_card(s["consumer_confidence"], steps=6, horizon_label="6 hónap múlva (becsült, az utolsó 36 hónap trendje alapján)", window=36),
    }

    r = load_json("realjovedelem.json")
    out["realjovedelem"] = {
        "years": r["years"][-12:],
        "wage_series": r["real_wage_yoy_pct"][-12:],
        "income_series": r["real_income_yoy_pct"][-12:],
        "years_full": r["years"],
        "wage_series_full": r["real_wage_yoy_pct"],
        "income_series_full": r["real_income_yoy_pct"],
        "wage_forecast": forecast_card(r["real_wage_yoy_pct"], steps=2, horizon_label="2 év múlva (becsült, az utolsó 10 év trendje alapján)", window=10),
        "income_forecast": forecast_card(r["real_income_yoy_pct"], steps=2, horizon_label="2 év múlva (becsült, az utolsó 10 év trendje alapján)", window=10),
    }

    return out


def build_hirek() -> dict:
    path = DATA_DIR / "hirek.json"
    if not path.exists():
        return {"generated": None, "articles": []}
    return load_json("hirek.json")


# A toplistában szereplő, de a config/segments.json example_brands listáiban NEM
# szereplő márkák kategóriája - CSAK a "Legkeresettebb modellek" fül
# megjelenítéséhez. Szándékosan nem a segments.json-t bővítjük: az
# example_brands hajtja a márkakategória-momentumot (engine.py), annak
# bővítése a szegmens-pontszámokat is megváltoztatná.
DISPLAY_BRAND_TIERS = {
    "Nissan": "tomeggyarto", "Kia": "tomeggyarto", "Renault": "tomeggyarto",
    "Peugeot": "tomeggyarto", "Citroen": "tomeggyarto", "Seat": "tomeggyarto",
    "Cupra": "tomeggyarto", "Mazda": "tomeggyarto", "Honda": "tomeggyarto",
    "Mitsubishi": "tomeggyarto", "Jeep": "tomeggyarto", "Mini": "premium",
    "Lexus": "premium", "Tesla": "premium", "Land Rover": "premium",
    "Porsche": "premium", "Chery": "kinai_belepo", "Omoda": "kinai_belepo",
    "Jaecoo": "kinai_belepo", "Leapmotor": "kinai_belepo", "Xpeng": "kinai_belepo",
}
MULTIWORD_BRANDS = ("Land Rover", "Alfa Romeo", "Aston Martin")


def model_brand(model: str) -> str:
    for b in MULTIWORD_BRANDS:
        if model.startswith(b + " "):
            return b
    return model.split(" ")[0]


def normalize_model(model: str) -> str:
    """Modellnév-egyeztetéshez: a zárójeles jelölések ("(teherautó)") nélkül."""
    return re.sub(r"\s*\([^)]*\)", "", model).strip(" –").lower()


def build_top_modellek(brand_summary: list[dict]) -> dict | None:
    """A kézi toplista kiegészítése: márka + márkakategória (a szegmens-
    pontszámmal együtt), helyezés-változás és havi darabszám az előző havi
    listához képest, piaci részesedés a forráscikk összpiaci számából."""
    path = DATA_DIR / "top_modellek.json"
    if not path.exists():
        return None
    tm = load_json("top_modellek.json")

    _, segments = load_config()
    tiers = segments["brand_tiers"]
    brand_to_tier = dict(DISPLAY_BRAND_TIERS)
    for tier_key, tier in tiers.items():
        for b in tier["example_brands"]:
            brand_to_tier[b] = tier_key
    tier_score = {r["key"]: r["score"] for r in brand_summary}

    prev = tm.get("previous") or {}
    prev_by_model = {}
    for r in prev.get("rows", []):
        # a forrásban előfordul ugyanaz a név kétszer (pl. két Tiggo 7 változat) -
        # a jobb helyezésűt tartjuk meg
        prev_by_model.setdefault(normalize_model(r["model"]), r)

    total = tm.get("market_total_units")
    for r in tm["rows"]:
        brand = model_brand(r["model"])
        tier_key = brand_to_tier.get(brand)
        r["brand"] = brand
        r["brand_tier"] = tier_key
        r["brand_tier_label"] = tiers[tier_key]["label"].split(" (")[0] if tier_key else None
        r["share_pct"] = round(r["units"] / total * 100, 2) if total else None
        p = prev_by_model.get(normalize_model(r["model"]))
        if prev.get("rows"):
            r["prev_rank"] = p["rank"] if p else None
            r["rank_change"] = (p["rank"] - r["rank"]) if p else None  # + = feljebb lépett
            r["period_units"] = (r["units"] - p["units"]) if p else None
    tm["tier_scores"] = {k: tier_score.get(k) for k in tiers}
    tm["tier_labels"] = {k: t["label"].split(" (")[0] for k, t in tiers.items()}
    return tm


def load_history(limit: int = HISTORY_LIMIT) -> list[dict]:
    """A korábbi futások pillanatképei, NAPONTA EGY bejegyzéssel (az adott
    nap utolsó futása). A snapshots.jsonl nyers archívum minden futást
    megtart; a deduplikálás csak a megjelenítéshez kell, hogy egy napon
    belüli kézi újrafuttatások ne torzítsák a trendgörbét."""
    if not HISTORY_PATH.exists():
        return []
    lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    by_date: dict[str, dict] = {}
    for line in lines:
        if line.strip():
            snap = json.loads(line)
            by_date[snap["date"]] = snap  # későbbi futás felülírja a korábbit
    return list(by_date.values())[-limit:]


REAL_HEADLINE_LABELS = {
    "benzin": ("Benzin ára", "Ft/l"),
    "dizel": ("Dízel ára", "Ft/l"),
    "alapkamat": ("Jegybanki alapkamat", "%"),
    "eurhuf": ("Euró/forint árfolyam", "Ft"),
    "forgalomba_total": ("Új forgalomba helyezések (negyedév)", "db"),
    "sentiment_mp": ("Vásárlási szándék", "pont"),
    "wage_yoy": ("Reálkereset változása", "%"),
}


def build_changes(prev: dict | None, combined: dict) -> dict | None:
    """Összevetés az előző NAPI futással: a szegmens-irányok (hajtástípus,
    márkakategória), az alap forgatókönyv tényező-értékei és a valós
    fő mutatók változásai. None, ha nincs korábbi napi futás."""
    if prev is None:
        return None
    items = []

    for group, key in (("Hajtástípus", "drivetrain_summary"), ("Márkakategória", "brand_summary")):
        prev_scores = {r["key"]: r["score"] for r in prev.get(key, [])}
        for r in combined[key]:
            if r["key"] not in prev_scores:
                continue
            old, new = prev_scores[r["key"]], r["score"]
            old_dir, new_dir = classify(old), r["dir"]
            if old_dir != new_dir or abs(new - old) >= 0.01:
                items.append({
                    "group": group, "label": r["label"], "unit": "pont",
                    "from": round(old * 100, 1), "to": round(new * 100, 1),
                    "from_dir": old_dir, "to_dir": new_dir,
                    "dir_changed": old_dir != new_dir,
                })

    prev_factors = prev.get("factors", {})
    for f in combined["factors"]:
        old = prev_factors.get(f["key"])
        if old is not None and abs(f["alap"] - old) >= 0.1:
            items.append({
                "group": "Tényező (alap)", "label": f["label"], "unit": f["unit"],
                "from": old, "to": f["alap"], "dir_changed": False,
            })

    prev_real = prev.get("real_headline", {})
    cur_real = build_real_headline(combined["real"])
    for key, (label, unit) in REAL_HEADLINE_LABELS.items():
        old, new = prev_real.get(key), cur_real.get(key)
        if old is not None and new is not None and old != new:
            items.append({
                "group": "Valós adat", "label": label, "unit": unit,
                "from": old, "to": new, "dir_changed": False,
            })

    # Irányváltások elöl, utána csoportonként az eredeti sorrend
    items.sort(key=lambda it: not it["dir_changed"])
    return {"since": prev["date"], "items": items}


def build_real_headline(real: dict) -> dict:
    return {
        "benzin": real["uzemanyagar"]["benzin_last"],
        "dizel": real["uzemanyagar"]["dizel_last"],
        "alapkamat": real["makro"]["alapkamat_last"],
        "eurhuf": real["makro"]["eurhuf_last"],
        "forgalomba_total": real["forgalomba"]["total_last"],
        "sentiment_mp": real["szentiment"]["mp_last"],
        "wage_yoy": real["realjovedelem"]["wage_series"][-1],
    }


def append_history_snapshot(combined: dict) -> None:
    factor_alap = {f["key"]: f["alap"] for f in combined["factors"]}
    real = combined["real"]
    entry = {
        "date": combined["generated"],
        "factors": factor_alap,
        "drivetrain_summary": [{"key": r["key"], "score": r["score"]} for r in combined["drivetrain_summary"]],
        "brand_summary": [{"key": r["key"], "score": r["score"]} for r in combined["brand_summary"]],
        "real_headline": build_real_headline(real),
    }
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    # A run_history-t a JELENLEGI snapshot hozzáfűzése ELŐTT töltjük be, hogy a
    # mai futás ne szerepeljen duplán a "korábbi futások" listájában.
    today = dt.date.today().isoformat()
    # A mai napi korábbi futás(ok) nem "korábbi futás": a mai állapotot a
    # jelenlegi build adja, a változás-blokk az előző NAPHOZ viszonyít.
    run_history = [s for s in load_history() if s["date"] != today]

    combined = {
        "generated": today,
        "coverage": {
            "n_factors": None,  # kitöltve lent
            "n_calibrated": len(CALIBRATED_FACTORS),
            "n_manual": len(MANUAL_SOURCE_FACTORS),
            "n_real_sources": len(AUTOMATED_SOURCES),
            "real_sources_label": " / ".join(sorted({s.split(" ")[0] for s in AUTOMATED_SOURCES})),
            "automation": "havonta, minden hónap 1-jén 10:00 (launchd) - adat-előkészítés automata, publikálás kézi kérésre",
        },
        **build_engine_summary(),
        "real": build_real_snapshot(),
        "run_history": run_history,
        "hirek": build_hirek(),
    }
    combined["top_modellek"] = build_top_modellek(combined["brand_summary"])
    combined["coverage"]["n_factors"] = len(combined["factors"])
    combined["methodology"] = build_methodology(combined["factors"])
    combined["changes"] = build_changes(run_history[-1] if run_history else None, combined)

    DATA_OUT_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    append_history_snapshot(combined)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__DASHBOARD_DATA__", json.dumps(combined, ensure_ascii=False, indent=2))
    HTML_OUT_PATH.write_text(html, encoding="utf-8")

    print(f"Dashboard adat frissítve: {DATA_OUT_PATH}")
    print(f"Dashboard HTML frissítve: {HTML_OUT_PATH} (publikálásra kész)")


if __name__ == "__main__":
    main()
