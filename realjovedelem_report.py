#!/usr/bin/env python3
"""
Valós reáljövedelem/vásárlóerő-trend riport a KSH gdp0035 adatból.

Előfeltétel: futtasd előbb a fetchers/fetch_realjovedelem.py-t.

Használat:
    python3 realjovedelem_report.py
Kimenet:
    reports/realjovedelem_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "realjovedelem.json"
REPORTS_DIR = Path(__file__).parent / "reports"


def build_report() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    years = data["years"]
    wage = data["real_wage_yoy_pct"]
    income = data["real_income_yoy_pct"]

    last_income_i = max(i for i, v in enumerate(income) if v is not None)
    last_wage_i = max(i for i, v in enumerate(wage) if v is not None)

    lines = []
    lines.append(f"# Reáljövedelem / vásárlóerő-trend riport — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(f"Forrás: KSH STADAT gdp0035 ({data['source_page']}).")
    lines.append(f"Megjegyzés: {data['note']}")
    lines.append("")

    lines.append("## Reáljövedelem (egy főre jutó, YoY)")
    lines.append("")
    lines.append(
        f"- Utolsó teljes adatév ({years[last_income_i]}): "
        f"**{income[last_income_i]:+.1f}%**"
    )
    lines.append("")

    lines.append("## Reálkereset (egy keresőre jutó, YoY)")
    lines.append("")
    lines.append(
        f"- Legfrissebb adatév ({years[last_wage_i]}): **{wage[last_wage_i]:+.1f}%**"
    )
    lines.append("")

    lines.append("## Utolsó 10 év alakulása")
    lines.append("")
    lines.append("| Év | Reálkereset YoY | Reáljövedelem YoY |")
    lines.append("|---|---|---|")
    for y, w, inc in list(zip(years, wage, income))[-10:]:
        w_str = f"{w:+.1f}%" if w is not None else "n/a"
        inc_str = f"{inc:+.1f}%" if inc is not None else "n/a"
        lines.append(f"| {y} | {w_str} | {inc_str} |")
    lines.append("")
    lines.append(
        "> A reáljövedelem (teljes, egy főre jutó vásárlóerő) a reálkeresetnél "
        "(csak a keresők bérjövedelme) szélesebb és jobb proxy a piaci "
        "keresletre, de egy évvel később publikálódik — ezért a legfrissebb "
        "évre gyakran csak a reálkereset áll rendelkezésre."
    )

    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report()
    out_path = REPORTS_DIR / f"realjovedelem_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
