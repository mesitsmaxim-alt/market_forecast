#!/usr/bin/env python3
"""
Üzemanyagár-trend riport.

Elsődleges forrás: holtankoljak.hu ÉLŐ, napi frissülő adata
(data/uzemanyagar_elo.json) — ez MINDIG a jelenlegi árat mutatja, ez hajtja
az oil_price tényező kalibrációját is (calibrate_factors.py).

Kiegészítés: a KSH régiós (HU vs. 9 szomszédos ország) összehasonlítás
(data/uzemanyagar.json) — ez viszont egy befagyott kiadvány-pillanatkép
(2023-01 – 2024-04), csak történeti/regionális kontextusnak, NEM élő adat.

Előfeltétel: futtasd előbb a fetchers/fetch_uzemanyag_elo.py-t (és
opcionálisan a fetchers/fetch_uzemanyagar.py-t a regionális szekcióhoz).

Használat:
    python3 fuel_report.py
Kimenet:
    reports/uzemanyag_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

LIVE_DATA_PATH = Path(__file__).parent / "data" / "uzemanyagar_elo.json"
REGIONAL_DATA_PATH = Path(__file__).parent / "data" / "uzemanyagar.json"
REPORTS_DIR = Path(__file__).parent / "reports"

HU = "Magyarország"


def build_live_section() -> list[str]:
    d = json.loads(LIVE_DATA_PATH.read_text(encoding="utf-8"))
    current, month_ago, year_ago = d["periods"]
    fuels = d["fuels"]

    lines = ["## Élő adat (holtankoljak.hu, mindig aktuális)", ""]
    lines.append(f"Utolsó frissítés: **{d['headline_date']}**")
    lines.append("")
    lines.append(
        f"- 95-ös benzin (mai országos átlag): **{d['headline']['benzin_95']} Ft/liter**"
    )
    lines.append(f"- Gázolaj (mai országos átlag): **{d['headline']['gazolaj']} Ft/liter**")
    lines.append("")
    lines.append(f"| Üzemanyag | {current} | {month_ago} | {year_ago} | Havi Δ | Éves (YoY) Δ |")
    lines.append("|---|---|---|---|---|---|")
    for name, vals in fuels.items():
        now, m_ago, y_ago = vals[current], vals[month_ago], vals[year_ago]
        m_delta = (now / m_ago - 1) * 100 if m_ago else float("nan")
        y_delta = (now / y_ago - 1) * 100 if y_ago else float("nan")
        lines.append(f"| {name} | {now} Ft | {m_ago} Ft | {y_ago} Ft | {m_delta:+.1f}% | {y_delta:+.1f}% |")
    lines.append("")
    lines.append(
        "> Ez az adat minden futáskor a ténylegesen aktuális árat tükrözi "
        "(nem egy régi pillanatfelvételt) — ez táplálja az `oil_price` "
        "forgatókönyv-tényező kalibrációját is."
    )
    lines.append("")
    return lines


def pct_change(series: list[float]) -> float:
    return (series[-1] / series[0] - 1) * 100


def regional_avg(prices: dict[str, list[float]], idx: int) -> float:
    values = [v[idx] for c, v in prices.items() if c != HU]
    return sum(values) / len(values)


def regional_fuel_section(label: str, block: dict) -> list[str]:
    weeks = block["weeks"]
    prices = block["prices"]
    hu = prices[HU]

    lines = [f"### {label}", ""]
    lines.append(
        f"- Magyar ár ({weeks[-1]}): **{hu[-1]} Ft/liter** "
        f"({weeks[0]} óta {pct_change(hu):+.1f}%)"
    )
    hu_avg_last = regional_avg(prices, -1)
    hu_avg_first = regional_avg(prices, 0)
    premium_last = (hu[-1] / hu_avg_last - 1) * 100
    premium_first = (hu[0] / hu_avg_first - 1) * 100
    lines.append(
        f"- Régiós átlaghoz képest ({weeks[-1]}): **{premium_last:+.1f}%** "
        f"(a periódus elején {premium_first:+.1f}% volt)"
    )
    lines.append("")
    lines.append("| Ország | Ár (legutóbbi) | Változás a periódus alatt |")
    lines.append("|---|---|---|")
    rows = sorted(prices.items(), key=lambda kv: kv[1][-1], reverse=True)
    for country, series in rows:
        marker = " **(HU)**" if country == HU else ""
        lines.append(f"| {country}{marker} | {series[-1]} Ft/l | {pct_change(series):+.1f}% |")
    lines.append("")
    return lines


def build_regional_section() -> list[str]:
    if not REGIONAL_DATA_PATH.exists():
        return []
    data = json.loads(REGIONAL_DATA_PATH.read_text(encoding="utf-8"))
    weeks = data["benzin"]["weeks"]

    lines = ["## Regionális összehasonlítás (KSH, történeti kontextus)", ""]
    lines.append(
        f"Forrás: KSH régiós üzemanyagár-összehasonlítás ({data['source_page']}). "
        f"Lefedett időszak: **{weeks[0]} – {weeks[-1]}** — ez egy befagyott "
        "kiadvány-pillanatkép, **NEM élő adat** (a fenti élő szekció adja a "
        "mindig aktuális árat). Csak a HU vs. szomszédos országok relatív "
        "pozíciójának történeti illusztrálására szolgál."
    )
    lines.append("")
    lines.extend(regional_fuel_section("95-ös benzin", data["benzin"]))
    lines.extend(regional_fuel_section("Dízel", data["dizel"]))
    return lines


def build_report() -> str:
    lines = [f"# Üzemanyagár-trend riport — {dt.date.today().isoformat()}", ""]
    lines.extend(build_live_section())
    lines.extend(build_regional_section())
    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report()
    out_path = REPORTS_DIR / f"uzemanyag_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
