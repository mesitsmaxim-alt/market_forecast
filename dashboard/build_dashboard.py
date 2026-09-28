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
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import compute_segments, classify, SCENARIOS  # noqa: E402
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


def load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def build_engine_summary() -> dict:
    results, factors = compute_segments()

    def agg(key_fn, label_fn):
        from collections import defaultdict
        buckets = defaultdict(lambda: {"pesszimista": [], "alap": [], "optimista": []})
        for r in results:
            b = buckets[key_fn(r)]
            for scenario in SCENARIOS:
                b[scenario].append(r.scores[scenario])
        out = []
        for k, scenario_scores in buckets.items():
            avg = {s: sum(vals) / len(vals) for s, vals in scenario_scores.items()}
            out.append({
                "key": k, "label": label_fn(k),
                "score": round(avg["alap"], 4), "dir": classify(avg["alap"]),
                "pesszimista": round(avg["pesszimista"], 4),
                "optimista": round(avg["optimista"], 4),
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
    }


def cagr(series: list[float], window: int) -> float:
    w = min(window, len(series) - 1)
    s, e = series[-1 - w], series[-1]
    if s <= 0:
        return 0.0
    return ((e / s) ** (1 / w) - 1) * 100


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
    current, month_ago, year_ago = ue["periods"]
    benzin_row = ue["fuels"]["95-ös Benzin E10"]
    dizel_row = ue["fuels"]["Gázolaj"]
    out["uzemanyagar"] = {
        "last_week": ue["headline_date"],
        "benzin_last": ue["headline"]["benzin_95"],
        "dizel_last": ue["headline"]["gazolaj"],
        "benzin_series": [benzin_row[year_ago], benzin_row[month_ago], benzin_row[current]],
        "dizel_series": [dizel_row[year_ago], dizel_row[month_ago], dizel_row[current]],
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


def build_top_modellek() -> dict | None:
    path = DATA_DIR / "top_modellek.json"
    if not path.exists():
        return None
    return load_json("top_modellek.json")


def load_history(limit: int = HISTORY_LIMIT) -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    snapshots = [json.loads(line) for line in lines if line.strip()]
    return snapshots[-limit:]


def append_history_snapshot(combined: dict) -> None:
    factor_alap = {f["key"]: f["alap"] for f in combined["factors"]}
    real = combined["real"]
    entry = {
        "date": combined["generated"],
        "factors": factor_alap,
        "drivetrain_summary": [{"key": r["key"], "score": r["score"]} for r in combined["drivetrain_summary"]],
        "brand_summary": [{"key": r["key"], "score": r["score"]} for r in combined["brand_summary"]],
        "real_headline": {
            "benzin": real["uzemanyagar"]["benzin_last"],
            "dizel": real["uzemanyagar"]["dizel_last"],
            "alapkamat": real["makro"]["alapkamat_last"],
            "eurhuf": real["makro"]["eurhuf_last"],
            "forgalomba_total": real["forgalomba"]["total_last"],
            "sentiment_mp": real["szentiment"]["mp_last"],
            "wage_yoy": real["realjovedelem"]["wage_series"][-1],
        },
    }
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    # A run_history-t a JELENLEGI snapshot hozzáfűzése ELŐTT töltjük be, hogy a
    # mai futás ne szerepeljen duplán a "korábbi futások" listájában.
    run_history = load_history()

    combined = {
        "generated": dt.date.today().isoformat(),
        "coverage": {
            "n_factors": None,  # kitöltve lent
            "n_calibrated": len(CALIBRATED_FACTORS),
            "n_manual": len(MANUAL_SOURCE_FACTORS),
            "n_real_sources": 6,
            "automation": "havonta, minden hónap 1-jén 10:00 (launchd) - adat-előkészítés automata, publikálás kézi kérésre",
        },
        **build_engine_summary(),
        "real": build_real_snapshot(),
        "run_history": run_history,
        "hirek": build_hirek(),
        "top_modellek": build_top_modellek(),
    }
    combined["coverage"]["n_factors"] = len(combined["factors"])

    DATA_OUT_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    append_history_snapshot(combined)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__DASHBOARD_DATA__", json.dumps(combined, ensure_ascii=False, indent=2))
    HTML_OUT_PATH.write_text(html, encoding="utf-8")

    print(f"Dashboard adat frissítve: {DATA_OUT_PATH}")
    print(f"Dashboard HTML frissítve: {HTML_OUT_PATH} (publikálásra kész)")


if __name__ == "__main__":
    main()
