#!/usr/bin/env python3
"""
Valós szegmentált trend-riport a KSH STADAT sza0025 adatból (2. lépés).

Ez a riport nem forgatókönyv-becslés (mint a generate_report.py), hanem
tényleges, megfigyelt piaci trendeket mutat be: hajtástípus és márka szerinti
állományváltozás (éves, illetve 5 éves CAGR).

Előfeltétel: futtasd előbb a fetchers/fetch_jarmuallomany.py-t.

Használat:
    python3 segment_report.py
Kimenet:
    reports/szegmens_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "jarmuallomany.json"
REPORTS_DIR = Path(__file__).parent / "reports"

FUEL_LABELS = {
    "benzin": "Benzin",
    "dizel": "Dízel",
    "hibrid": "Hibrid (nem tölthető)",
    "elektromos": "Tisztán elektromos",
    "egyeb": "Egyéb",
}


def yoy(series: list[float]) -> float:
    return (series[-1] / series[-2] - 1) * 100


def cagr(series: list[float], n_years: int) -> float:
    start, end = series[-1 - n_years], series[-1]
    if start <= 0:
        return float("nan")
    return ((end / start) ** (1 / n_years) - 1) * 100


def share(value: float, total: float) -> float:
    return value / total * 100


def build_report() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    years = data["years"]
    total = data["total"]
    brands = data["brands"]
    fuel_types = data["fuel_types"]

    last_year = years[-1]
    cagr_window = min(5, len(years) - 1)

    lines = []
    lines.append(f"# Autópiaci szegmens-riport (KSH-adat alapján) — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(
        f"Forrás: KSH STADAT sza0025 — személygépkocsi-állomány gyártmány és "
        f"üzemanyag-felhasználás szerint ({data['source_page']}). "
        f"Utolsó adatév: {last_year}."
    )
    lines.append("")

    lines.append("## 1. Teljes állomány")
    lines.append("")
    lines.append(
        f"- Összesen ({last_year}): **{total[-1]:,}** db "
        f"(előző évhez képest {yoy(total):+.1f}%, {cagr_window} éves CAGR: {cagr(total, cagr_window):+.1f}%/év)"
    )
    lines.append("")

    lines.append("## 2. Hajtástípus szerinti trend")
    lines.append("")
    lines.append("| Hajtástípus | Megoszlás (" + str(last_year) + ") | YoY | " + f"{cagr_window} éves CAGR" + " |")
    lines.append("|---|---|---|---|")
    fuel_rows = []
    for key, series in fuel_types.items():
        label = FUEL_LABELS.get(key, key)
        fuel_rows.append(
            (label, share(series[-1], total[-1]), yoy(series), cagr(series, cagr_window))
        )
    fuel_rows.sort(key=lambda r: r[3], reverse=True)
    for label, sh, y, c in fuel_rows:
        lines.append(f"| {label} | {sh:.1f}% | {y:+.1f}% | {c:+.1f}%/év |")
    lines.append("")
    lines.append(
        "> A CAGR (összetett éves növekedési ütem) jobban mutatja az alapirányt, "
        "mint egyetlen év YoY-ja, amit rövid távú ingadozás torzíthat."
    )
    lines.append("")

    lines.append("## 3. Márkák szerinti trend (top 15 állomány szerint)")
    lines.append("")
    lines.append(f"| Márka | Piaci részesedés ({last_year}) | YoY | {cagr_window} éves CAGR |")
    lines.append("|---|---|---|---|")
    brand_rows = []
    for brand, series in brands.items():
        brand_rows.append(
            (brand, series[-1], share(series[-1], total[-1]), yoy(series), cagr(series, cagr_window))
        )
    brand_rows.sort(key=lambda r: r[1], reverse=True)
    for brand, _, sh, y, c in brand_rows[:15]:
        lines.append(f"| {brand} | {sh:.1f}% | {y:+.1f}% | {c:+.1f}%/év |")
    lines.append("")

    lines.append("## 4. Leggyorsabban növekvő és csökkenő márkák (5 éves CAGR, min. 5000 db állomány)")
    lines.append("")
    eligible = [r for r in brand_rows if r[1] >= 5000]
    eligible_sorted = sorted(eligible, key=lambda r: r[4], reverse=True)
    lines.append("**Növekvők:**")
    for brand, _, sh, y, c in eligible_sorted[:5]:
        lines.append(f"- {brand}: {c:+.1f}%/év (részesedés {sh:.1f}%)")
    lines.append("")
    lines.append("**Csökkenők:**")
    for brand, _, sh, y, c in eligible_sorted[-5:][::-1]:
        lines.append(f"- {brand}: {c:+.1f}%/év (részesedés {sh:.1f}%)")
    lines.append("")

    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report()
    out_path = REPORTS_DIR / f"szegmens_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
