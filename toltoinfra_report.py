#!/usr/bin/env python3
"""
Valós töltőinfrastruktúra-trend riport az EAFO (kézzel importált) adatból.

Előfeltétel: futtasd előbb az import_eafo_charging.py-t (ami a kézzel
exportált CSV-ket dolgozza fel).

Használat:
    python3 toltoinfra_report.py
Kimenet:
    reports/toltoinfra_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "toltoinfra.json"
REPORTS_DIR = Path(__file__).parent / "reports"


def yoy_from_quarters(values: list[float]) -> float:
    if len(values) < 5:
        return float("nan")
    return (values[-1] / values[-5] - 1) * 100


def build_report() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    qc = data["quarterly_counts"]
    quarters, ac, dc = qc["quarters"], qc["ac"], qc["dc"]
    total = [a + d for a, d in zip(ac, dc)]

    lines = []
    lines.append(f"# Töltőinfrastruktúra-trend riport — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(f"Forrás: EAFO, kézzel exportálva ({data['source_page']}).")
    lines.append(f"Utolsó adat-negyedév: {quarters[-1]}.")
    lines.append("")

    lines.append("## Összes nyilvános töltőpont (AC + DC)")
    lines.append("")
    lines.append(
        f"- Jelenlegi ({quarters[-1]}): **{int(total[-1])} db** "
        f"(AC: {int(ac[-1])}, DC: {int(dc[-1])})"
    )
    lines.append(f"- Éves (YoY) változás: **{yoy_from_quarters(total):+.1f}%**")
    lines.append(f"  - AC: {yoy_from_quarters(ac):+.1f}% | DC: {yoy_from_quarters(dc):+.1f}%")
    lines.append("")
    lines.append(
        "> A DC (gyorstöltő) állomány jellemzően gyorsabban nő, mint az AC "
        "— ez összhangban van azzal, hogy a hálózatbővítés a BEV-használat "
        "gyakorlati akadályait (hosszú töltési idő) próbálja csökkenteni."
    )
    lines.append("")

    lines.append("## Negyedéves alakulás (utolsó 8 negyedév)")
    lines.append("")
    lines.append("| Negyedév | AC | DC | Összesen |")
    lines.append("|---|---|---|---|")
    for q, a, d in list(zip(quarters, ac, dc))[-8:]:
        lines.append(f"| {q} | {int(a)} | {int(d)} | {int(a + d)} |")
    lines.append("")

    lines.append("## DC töltők teljesítmény-kategória szerint (év végi állapot)")
    lines.append("")
    dc_power = data["dc_by_power_yearly"]
    years = dc_power["years"]
    lines.append("| Év | " + " | ".join(dc_power["series"].keys()) + " |")
    lines.append("|---|" + "---|" * len(dc_power["series"]))
    for i, year in enumerate(years):
        row = [str(int(series[i])) for series in dc_power["series"].values()]
        lines.append(f"| {year} | " + " | ".join(row) + " |")
    lines.append("")
    lines.append(
        "> Jól látszik az ultragyors (150kW+) DC-töltők arányának gyors "
        "növekedése az elmúlt években, ami a hosszabb távú BEV-használatot "
        "(pl. autópályás töltést) könnyíti meg."
    )

    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report()
    out_path = REPORTS_DIR / f"toltoinfra_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
