#!/usr/bin/env python3
"""
Valós, negyedéves forgalomba helyezési trend riport a KSH sza0070 adatból.

Ez a lassan mozgó állomány-adat (sza0025) gyors, előretekintő kiegészítője:
a friss forgalomba helyezés azonnal mutatja, merre fordul a piac.

Előfeltétel: futtasd előbb a fetchers/fetch_forgalomba.py-t.

Használat:
    python3 forgalomba_report.py
Kimenet:
    reports/forgalomba_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "forgalomba.json"
REPORTS_DIR = Path(__file__).parent / "reports"


def yoy(series: list[float]) -> float:
    """Azonos negyedév előző évhez képest (4 negyedéves eltolással), a szezonalitás kiküszöbölésére."""
    if len(series) < 5:
        return float("nan")
    return (series[-1] / series[-5] - 1) * 100


def build_report() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    quarters, total, brands = data["quarters"], data["total"], data["brands"]

    lines = []
    lines.append(f"# Forgalomba helyezési trend riport — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(f"Forrás: KSH STADAT sza0070 ({data['source_page']}).")
    lines.append(f"Utolsó adat-negyedév: {quarters[-1]}.")
    lines.append("")

    lines.append("## Összes első forgalomba helyezés")
    lines.append("")
    lines.append(f"- Jelenlegi ({quarters[-1]}): **{total[-1]:,} db**")
    lines.append(f"- Azonos negyedév előző évhez képest (YoY): **{yoy(total):+.1f}%**")
    lines.append("")
    lines.append("| Negyedév | Darabszám |")
    lines.append("|---|---|")
    for q, t in list(zip(quarters, total))[-8:]:
        lines.append(f"| {q} | {t:,} |")
    lines.append("")

    lines.append("## Márkák szerinti trend (top 15 forgalomba helyezés szerint, YoY)")
    lines.append("")
    lines.append(f"| Márka | {quarters[-1]} | YoY |")
    lines.append("|---|---|---|")
    brand_rows = sorted(brands.items(), key=lambda kv: kv[1][-1], reverse=True)
    for brand, series in brand_rows[:15]:
        lines.append(f"| {brand} | {series[-1]:,} | {yoy(series):+.1f}% |")
    lines.append("")

    lines.append("## Leggyorsabban változó márkák (YoY, min. 500 db a legutóbbi negyedévben)")
    lines.append("")
    eligible = [(b, s) for b, s in brands.items() if s[-1] >= 500 and len(s) >= 5]
    eligible_sorted = sorted(eligible, key=lambda bs: yoy(bs[1]), reverse=True)
    lines.append("**Növekvők:**")
    for brand, series in eligible_sorted[:5]:
        lines.append(f"- {brand}: {yoy(series):+.1f}% ({series[-1]:,} db)")
    lines.append("")
    lines.append("**Csökkenők:**")
    for brand, series in eligible_sorted[-5:][::-1]:
        lines.append(f"- {brand}: {yoy(series):+.1f}% ({series[-1]:,} db)")
    lines.append("")
    lines.append(
        "> Ez az adat gyorsabban reagál a piaci elmozdulásokra, mint az "
        "állomány-adat (`szegmens_riport_...`), de negyedéves szinten "
        "zajosabb is — egy-egy nagy flottavásárlás vagy modellváltás "
        "kiugró negyedévet okozhat egy-egy márkánál."
    )

    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report()
    out_path = REPORTS_DIR / f"forgalomba_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
