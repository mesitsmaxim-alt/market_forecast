#!/usr/bin/env python3
"""
Backtesting: a config/segments.json-ban kézzel megadott érzékenységi
együtthatók visszamérése valós, történeti KSH/MNB/Eurostat adaton.

Módszertan
----------
A modell 8 tényezőjéből csak 4-hez van elég hosszú, éves bontású valós
történeti idősorunk ahhoz, hogy évről évre kiszámoljuk a tényleges deltát:

    - financing_cost   <- MNB alapkamat (év végi érték, éves változás)
    - purchasing_power <- KSH reáljövedelem/reálkereset YoY%
    - consumer_sentiment <- Eurostat "vásárlási szándék", éves átlag, éves változás
    - oil_price        <- Eurostat HICP üzemanyagindex, éves átlagos YoY%

(Az akkumulátorár, töltőinfra, EV-vám, CO2-szabályozás tényezőkhöz
nincs elég hosszú visszamenő valós idősor a projektben - ez a backtest tehát
CSAK a modell egy részét, nem az egészet teszteli. Ez explicit korlát, nem
elhallgatott hiba.)

A FONTOS MÓDSZERTANI DÖNTÉS: a "megfigyelt piaci momentum" tagot (engine.py)
szándékosan KIHAGYJUK a backtestből, mert azt is ugyanabból a KSH
állomány-idősorból számoljuk, amit itt "tényleges kimenetként" használunk -
a momentum bevonása körkörös (a múltbeli trendből "megjósolná" a múltbeli
trendet). A backtest tehát kifejezetten azt teszteli, hogy a FORGATÓKÖNYV-
TÉNYEZŐK (a modell voltaképpeni új információtartalma a nyers trendhez
képest) helyesen jelzik-e előre a tényleges elmozdulás irányát/mértékét.

Kimenet-metrika: minden évre (2003-2025) kiszámoljuk
    actual_diff  = (BEV részesedés-változás, százalékpont) - (ICE részesedés-változás, százalékpont)
    predicted_diff = (BEV pontszám) - (ICE pontszám) a 3 tényezőből, a
                     config/segments.json érzékenységeivel (a 4 tényezőből)
majd Pearson-korrelációt és "hit rate"-et (hányszor egyezik az előjel)
számolunk. Ugyanezt megismételjük Hibrid vs. ICE összevetésre is.

Használat:
    python3 backtest.py
Kimenet:
    reports/backtest_riport.md
"""

from __future__ import annotations

import datetime
import json
import math
import statistics
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CONFIG_DIR = Path(__file__).parent / "config"
REPORTS_DIR = Path(__file__).parent / "reports"

TESTED_FACTORS = ["financing_cost", "purchasing_power", "consumer_sentiment", "oil_price"]
SIGNIFICANCE = 0.05  # e fölötti p-értéknél a riport nem állíthat "jobb a véletlennél"-t


def load_json(name: str, base: Path = DATA_DIR) -> dict:
    return json.loads((base / name).read_text(encoding="utf-8"))


def rate_at_year_end(rate_dates, rate_vals, year):
    target = datetime.date(year, 12, 31)
    candidates = [(d, v) for d, v in zip(rate_dates, rate_vals) if d <= target]
    return candidates[-1][1] if candidates else None


def build_year_factor_deltas():
    """Éves szintű, TÉNYLEGES (nem forgatókönyv-becsült) tényező-deltákat ad
    vissza {év: {financing_cost, purchasing_power, consumer_sentiment}} alakban,
    csak azokra az évekre, ahol mindhárom rendelkezésre áll."""
    m = load_json("makro.json")
    rate_dates = [datetime.date.fromisoformat(d) for d in m["alapkamat"]["dates"]]
    rate_vals = m["alapkamat"]["values"]

    r = load_json("realjovedelem.json")
    income_by_year = dict(zip(r["years"], r["real_income_yoy_pct"]))
    wage_by_year = dict(zip(r["years"], r["real_wage_yoy_pct"]))

    s = load_json("szentiment.json")
    mp_by_month = dict(zip(s["months"], s["major_purchases_intention"]))

    def mp_avg_year(year):
        vals = [v for k, v in mp_by_month.items() if k.startswith(str(year)) and v is not None]
        return sum(vals) / len(vals) if vals else None

    # üzemanyagár: az Eurostat HICP-üzemanyag éves átlagos változása (%) - az
    # élő kútár-adatnak (oil_price kalibráció) nincs hosszú múltja
    fuel = load_json("uzemanyag_index.json")
    fuel_by_year = dict(zip(fuel["annual_years"], fuel["annual_avg_yoy_pct"]))

    j = load_json("jarmuallomany.json")
    years = j["years"]

    out = {}
    for i in range(1, len(years)):
        y, y0 = years[i], years[i - 1]
        r1 = rate_at_year_end(rate_dates, rate_vals, y)
        r0 = rate_at_year_end(rate_dates, rate_vals, y0)
        fin_delta = (r1 - r0) if r1 is not None and r0 is not None else None

        pp_delta = income_by_year.get(y, wage_by_year.get(y))

        sy, sy0 = mp_avg_year(y), mp_avg_year(y0)
        sent_delta = (sy - sy0) if sy is not None and sy0 is not None else None

        oil_delta = fuel_by_year.get(y)

        if None in (fin_delta, pp_delta, sent_delta, oil_delta):
            continue
        out[y] = {
            "financing_cost": fin_delta,
            "purchasing_power": pp_delta,
            "consumer_sentiment": sent_delta,
            "oil_price": oil_delta,
        }
    return out, j


def binom_two_sided_p(k: int, n: int) -> float:
    """Kétoldali egzakt binomiális próba p = 0,5 mellett (a találati arány
    eltér-e a véletlentől)."""
    tail = sum(math.comb(n, i) for i in range(max(k, n - k), n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def corr_p_value(r: float, n: int) -> float:
    """Kétoldali p-érték a Pearson-korrelációra, Fisher-z normális közelítéssel
    (stdlib: nincs t-eloszlás; n ≈ 20 fölött a különbség elhanyagolható)."""
    r = max(-0.999999, min(0.999999, r))
    z = math.atanh(r) * math.sqrt(n - 3)
    return 2 * (1 - statistics.NormalDist().cdf(abs(z)))


def score(sensitivity: dict, deltas: dict) -> float:
    return sum(sensitivity.get(f, 0.0) * deltas[f] / 100.0 for f in TESTED_FACTORS)


def run_backtest(label_a: str, ksh_keys_a: list[str], sens_a: dict,
                  label_b: str, ksh_keys_b: list[str], sens_b: dict,
                  year_deltas: dict, jarmuallomany: dict) -> dict:
    years = jarmuallomany["years"]
    total = jarmuallomany["total"]
    fuel = jarmuallomany["fuel_types"]

    def share(keys, i):
        return sum(fuel[k][i] for k in keys) / total[i] * 100

    rows = []
    for i in range(1, len(years)):
        y = years[i]
        if y not in year_deltas:
            continue
        actual_diff = (share(ksh_keys_a, i) - share(ksh_keys_a, i - 1)) - \
                      (share(ksh_keys_b, i) - share(ksh_keys_b, i - 1))
        predicted_diff = score(sens_a, year_deltas[y]) - score(sens_b, year_deltas[y])
        rows.append({
            "year": y,
            "actual_diff": actual_diff,
            "predicted_diff": predicted_diff,
            "sign_match": (actual_diff >= 0) == (predicted_diff >= 0),
        })

    actual = [r["actual_diff"] for r in rows]
    predicted = [r["predicted_diff"] for r in rows]
    corr = statistics.correlation(actual, predicted) if len(rows) > 2 else None
    hits = sum(r["sign_match"] for r in rows)
    hit_rate = hits / len(rows) if rows else None
    # a marginálisokból várható véletlen egyezés: ha a tényleges és a jósolt
    # előjel is többnyire pozitív, a "találat" 50%-nál gyakrabban jön véletlenül
    pa = sum(a >= 0 for a in actual) / len(rows) if rows else None
    pp = sum(p >= 0 for p in predicted) / len(rows) if rows else None

    return {
        "label": f"{label_a} vs. {label_b}", "rows": rows, "correlation": corr, "hit_rate": hit_rate,
        "hit_p": binom_two_sided_p(hits, len(rows)) if rows else None,
        "corr_p": corr_p_value(corr, len(rows)) if corr is not None and len(rows) > 3 else None,
        "actual_pos_share": pa,
        "chance_hit": pa * pp + (1 - pa) * (1 - pp) if rows else None,
    }


def build_report(results: list[dict]) -> str:
    lines = []
    lines.append(f"# Backtesting — {datetime.date.today().isoformat()}")
    lines.append("")
    lines.append(
        "A `config/segments.json`-ban kézzel megadott érzékenységi együtthatók "
        "visszamérése valós, történeti adaton. **Csak 4 a 8 tényezőből tesztelhető** "
        "(finanszírozási költség, vásárlóerő, fogyasztói szándék, üzemanyagár — az "
        "utóbbi az Eurostat HICP-üzemanyagindexéből) — ehhez van elég hosszú, éves "
        "bontású valós idősorunk. A többi tényezőhöz (akkumulátorár, töltőinfra, "
        "EV-vám, CO2-szabályozás) nincs elég hosszú "
        "visszamenő adat a projektben, ezért ez a backtest **a modell egy "
        "részét, nem az egészét** validálja."
    )
    lines.append("")
    lines.append(
        "> **Módszertani megjegyzés:** a \"megfigyelt piaci momentum\" tag "
        "(`engine.py`) szándékosan KI van hagyva ebből a tesztből. A hajtás-"
        "momentum ma már az új autók hajtás szerinti részesedéséből jön "
        "(Eurostat, csak 2020-tól), nem az itt kimenetként használt KSH-"
        "állományból, de ugyanazt a piaci átrendeződést méri, így bevonása "
        "részben körkörös lenne, és a 2020 előtti évekre nincs is adata. A "
        "backtest tehát kifejezetten azt méri, van-e előrejelző ereje a "
        "forgatókönyv-tényezőknek ÖNMAGUKBAN, a nyers trendtől függetlenül."
    )
    lines.append("")

    for res in results:
        lines.append(f"## {res['label']}")
        lines.append("")
        corr_txt = f"{res['correlation']:+.2f}" if res["correlation"] is not None else "n/a"
        hit_txt = f"{res['hit_rate']*100:.0f}%" if res["hit_rate"] is not None else "n/a"
        lines.append(f"- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): {corr_txt}")
        lines.append(f"- **Hit rate** (előjel-egyezés): {hit_txt} (n={len(res['rows'])} év, véletlen alapérték: 50%)")
        lines.append("")
        lines.append("| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |")
        lines.append("|---|---|---|---|")
        for r in res["rows"]:
            mark = "✅" if r["sign_match"] else "❌"
            lines.append(
                f"| {r['year']} | {r['actual_diff']:+.3f} | {r['predicted_diff']:+.5f} | {mark} |"
            )
        lines.append("")

    lines.append("## Értelmezés")
    lines.append("")
    # Az értelmezés a tényleges számokból készül, nem fix szöveg - különben egy
    # romló eredmény mellett is "a véletlennél jobb"-at állítana.
    # A "jobb a véletlennél" állítás csak szignifikáns (p < SIGNIFICANCE) eredményre
    # mehet ki: korábban egy fix 60%-os küszöb a 14/23-as (p = 0,40) találatra is
    # "érdemben jobb a véletlennél"-t írt.
    for res in results:
        corr, hit = res["correlation"], res["hit_rate"]
        if corr is None or hit is None:
            continue
        n = len(res["rows"])
        if res["hit_p"] < SIGNIFICANCE:
            hit_txt = (f"szignifikánsan {'jobb' if hit > 0.5 else 'rosszabb'} a véletlennél "
                       f"(50%; p = {res['hit_p']:.3f})")
        else:
            hit_txt = (f"statisztikailag nem különböztethető meg a véletlentől "
                       f"(50%; p = {res['hit_p']:.2f}, n = {n})")
        if res["corr_p"] < SIGNIFICANCE:
            corr_txt = f"szignifikáns (p = {res['corr_p']:.3f}), a pontszámok nagyságrendje követi a tényleges elmozdulást"
        else:
            corr_txt = (f"nem különböztethető meg a nullától (p = {res['corr_p']:.2f}), "
                        f"a pontszámok nagyságrendje nem bizonyíthatóan követi a tényleges elmozdulást")
        lines.append(
            f"- **{res['label']}:** a találati arány ({hit*100:.0f}%) {hit_txt}; a korreláció "
            f"({corr:+.2f}) {corr_txt}. Mivel a tényleges változás {res['actual_pos_share']*100:.0f}%-ban "
            f"pozitív, a véletlen egyezés várható aránya valójában {res['chance_hit']*100:.0f}%."
        )
    lines.append("")
    lines.append(
        "Az érzékenységi együtthatók szakértői becslések. Ha az eredmény nem "
        "szignifikáns, két magyarázat lehetséges, és a backtest nem dönt köztük: (1) a "
        "BEV-térnyerés tényleges mozgatórugói (akkumulátorár, töltőinfra, "
        "EU-szabályozás) pont azok, amikhez nincs hosszú történeti adatunk, ezért a "
        "backtest vak foltokkal dolgozik; (2) a tesztelt tényezők együtthatóinak "
        "nincs kimutatható előrejelző ereje. A p-értékek ráadásul optimisták: az "
        "állomány-részesedés éves változásai erősen autokorreláltak, így a független "
        "megfigyelések száma kisebb, mint n."
    )

    return "\n".join(lines)


def main():
    segments = load_json("segments.json", CONFIG_DIR)
    drivetrains = segments["drivetrains"]

    year_deltas, jarmuallomany = build_year_factor_deltas()

    results = [
        run_backtest(
            "BEV", ["elektromos"], drivetrains["BEV"]["sensitivity"],
            "ICE", ["benzin", "dizel"], drivetrains["ICE"]["sensitivity"],
            year_deltas, jarmuallomany,
        ),
        run_backtest(
            "Hibrid", ["hibrid"], drivetrains["HEV"]["sensitivity"],
            "ICE", ["benzin", "dizel"], drivetrains["ICE"]["sensitivity"],
            year_deltas, jarmuallomany,
        ),
    ]

    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report(results)
    out_path = REPORTS_DIR / "backtest_riport.md"
    out_path.write_text(content, encoding="utf-8")

    # Gépileg olvasható összefoglaló a dashboard módszertani blokkjához
    # (a markdown riport mellett; a run_pipeline.sh a dashboard ELŐTT futtatja).
    summary = {
        "generated": datetime.date.today().isoformat(),
        "tested_factors": list(TESTED_FACTORS),
        "comparisons": [{
            "label": res["label"],
            "correlation": round(res["correlation"], 3) if res["correlation"] is not None else None,
            "hit_rate": round(res["hit_rate"], 3) if res["hit_rate"] is not None else None,
            "hit_p": round(res["hit_p"], 3) if res["hit_p"] is not None else None,
            "corr_p": round(res["corr_p"], 3) if res["corr_p"] is not None else None,
            "significant": bool(
                res["hit_p"] is not None and res["hit_p"] < SIGNIFICANCE and res["hit_rate"] > 0.5
            ),
            "n": len(res["rows"]),
            "first_year": res["rows"][0]["year"] if res["rows"] else None,
            "last_year": res["rows"][-1]["year"] if res["rows"] else None,
        } for res in results],
    }
    (DATA_DIR / "backtest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    for res in results:
        corr = f"{res['correlation']:+.2f}" if res["correlation"] is not None else "n/a"
        hit = f"{res['hit_rate']*100:.0f}%" if res["hit_rate"] is not None else "n/a"
        print(f"{res['label']}: korreláció={corr}, hit rate={hit} (n={len(res['rows'])})")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
