#!/usr/bin/env python3
"""
Valós fogyasztói szentiment-trend riport az Eurostat adatból.

Előfeltétel: futtasd előbb a fetchers/fetch_szentiment.py-t.

Használat:
    python3 szentiment_report.py
Kimenet:
    reports/szentiment_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "szentiment.json"
REPORTS_DIR = Path(__file__).parent / "reports"


def change_1y(series: list[float]) -> float:
    if len(series) < 13:
        return float("nan")
    return series[-1] - series[-13]


def build_report() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    months = data["months"]
    mp = data["major_purchases_intention"]
    cc = data["consumer_confidence"]

    lines = []
    lines.append(f"# Fogyasztói szentiment-trend riport — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(f"Forrás: Eurostat ei_bsco_m ({data['source']}).")
    lines.append(f"Utolsó adat-hónap: {months[-1]}. Egység: {data['unit']}.")
    lines.append("")
    lines.append(
        "> Ez az egyetlen **előretekintő** indikátor a rendszerben: nem azt "
        "méri, mi történt, hanem hogy az emberek mit terveznek a következő "
        "12 hónapban. A \"tartós fogyasztási cikk vásárlási szándék\" a "
        "legjobb elérhető autópiaci proxy (nincs autó-specifikus kérdés az "
        "EU-felmérésben)."
    )
    lines.append("")

    lines.append("## Tartós fogyasztási cikk vásárlási szándék (autópiaci proxy)")
    lines.append("")
    lines.append(f"- Jelenlegi ({months[-1]}): **{mp[-1]:+.1f}** (balance-mutató)")
    lines.append(f"- 1 évvel korábban: {mp[-13]:+.1f}")
    lines.append(f"- Változás: **{change_1y(mp):+.1f} pont/év**")
    lines.append("")

    lines.append("## Általános fogyasztói bizalmi index")
    lines.append("")
    lines.append(f"- Jelenlegi ({months[-1]}): **{cc[-1]:+.1f}**")
    lines.append(f"- 1 évvel korábban: {cc[-13]:+.1f}")
    lines.append(f"- Változás: **{change_1y(cc):+.1f} pont/év**")
    lines.append("")

    lines.append("## Utolsó 12 hónap alakulása")
    lines.append("")
    lines.append("| Hónap | Vásárlási szándék | Fogyasztói bizalom |")
    lines.append("|---|---|---|")
    for m, p, c in list(zip(months, mp, cc))[-12:]:
        lines.append(f"| {m} | {p:+.1f} | {c:+.1f} |")
    lines.append("")
    lines.append(
        "> A balance-mutató a pozitív és negatív válaszok különbsége "
        "(-100..+100 skálán, gyakorlatban jellemzően -40..+10 közötti "
        "tartományban mozog) — a 0 fölötti érték nem \"jó\", hanem a "
        "hosszú távú átlaghoz és a korábbi hónapokhoz viszonyítva kell "
        "értelmezni a trendet."
    )

    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report()
    out_path = REPORTS_DIR / f"szentiment_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
