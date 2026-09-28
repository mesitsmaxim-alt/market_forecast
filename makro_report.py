#!/usr/bin/env python3
"""
Valós makró-trend riport (MNB alapkamat + EUR/HUF árfolyam) alapján.

Előfeltétel: futtasd előbb a fetchers/fetch_makro.py-t.

Használat:
    python3 makro_report.py
Kimenet:
    reports/makro_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "makro.json"
REPORTS_DIR = Path(__file__).parent / "reports"


def rate_one_year_ago(dates: list[str], values: list[float]) -> float:
    last_date = dt.date.fromisoformat(dates[-1])
    target = last_date - dt.timedelta(days=365)
    # az utolsó olyan bejegyzés, ami a cél-dátumnál nem későbbi
    candidates = [(d, v) for d, v in zip(dates, values) if dt.date.fromisoformat(d) <= target]
    return candidates[-1][1] if candidates else values[0]


def build_report() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rate = data["alapkamat"]
    fx = data["eur_huf_havi"]

    current_rate = rate["values"][-1]
    rate_1y_ago = rate_one_year_ago(rate["dates"], rate["values"])
    rate_change_pp = current_rate - rate_1y_ago

    current_fx = fx["values"][-1]
    fx_1y_ago = fx["values"][-13] if len(fx["values"]) >= 13 else fx["values"][0]
    fx_change_pct = (current_fx / fx_1y_ago - 1) * 100

    lines = []
    lines.append(f"# Makró-trend riport — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(f"Forrás: MNB — {rate['source']} , {fx['source']}")
    lines.append("")
    lines.append("## Jegybanki alapkamat")
    lines.append("")
    lines.append(f"- Jelenlegi ({rate['dates'][-1]}): **{current_rate:.2f}%**")
    lines.append(f"- 1 évvel korábban: {rate_1y_ago:.2f}%")
    lines.append(f"- Változás: **{rate_change_pp:+.2f} százalékpont**/év")
    lines.append("")
    lines.append("| Hatályba lépés | Alapkamat |")
    lines.append("|---|---|")
    for d, v in list(zip(rate["dates"], rate["values"]))[-8:][::-1]:
        lines.append(f"| {d} | {v:.2f}% |")
    lines.append("")

    lines.append("## EUR/HUF árfolyam (havi átlag)")
    lines.append("")
    lines.append(f"- Jelenlegi ({fx['months'][-1]}): **{current_fx:.2f} Ft**")
    lines.append(f"- 1 évvel korábban: {fx_1y_ago:.2f} Ft")
    lines.append(f"- Változás: **{fx_change_pct:+.1f}%** (forintgyengülés, ha pozitív)")
    lines.append("")
    lines.append("| Hónap | EUR/HUF |")
    lines.append("|---|---|")
    for m, v in list(zip(fx["months"], fx["values"]))[-12:][::-1]:
        lines.append(f"| {m} | {v:.2f} |")
    lines.append("")
    lines.append(
        "> A gyengülő forint az importált (jellemzően nem hazai gyártású, "
        "így pl. importált BEV-modelleket erősebben érintő) járművek "
        "beszerzési költségét emeli, a kamatcsökkenés/emelkedés pedig a "
        "hitelből/lízingből vásárolt (jellemzően új, drágább) autók "
        "keresletére hat."
    )

    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    content = build_report()
    out_path = REPORTS_DIR / f"makro_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
