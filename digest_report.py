#!/usr/bin/env python3
"""
Egyoldalas, gyorsan átfutható összefoglaló (digest) a legfrissebb futásról.

A cél: ne kelljen 8 külön riportfájlt megnyitni ahhoz, hogy valaki lássa,
történt-e valami érdemi változás. Ez a dashboard/dashboard_data.json-ból
építkezik (előbb azt kell frissíteni: dashboard/build_dashboard.py).

Használat:
    python3 digest_report.py
Kimenet:
    reports/DIGEST.md  (mindig felülíródik, ez a "legfrissebb állapot")
    stdout: rövid szöveges összefoglaló (a macOS értesítéshez is ezt használja a run_pipeline.sh)
"""

from __future__ import annotations

import json
from pathlib import Path

DASHBOARD_DATA_PATH = Path(__file__).parent / "dashboard" / "dashboard_data.json"
REPORTS_DIR = Path(__file__).parent / "reports"
OUT_PATH = REPORTS_DIR / "DIGEST.md"


def build_digest() -> tuple[str, str]:
    """Visszaadja a (markdown, rövid egysoros értesítés-szöveg) párost."""
    d = json.loads(DASHBOARD_DATA_PATH.read_text(encoding="utf-8"))
    cov = d["coverage"]
    real = d["real"]

    top_dt = d["drivetrain_summary"][0]
    top_winner = d["top_winners"][0]

    lines = []
    lines.append(f"# Piaci előrejelző — heti/havi digest ({d['generated']})")
    lines.append("")
    lines.append(
        f"**Lefedettség:** {cov['n_calibrated'] + cov.get('n_manual', 0)}/{cov['n_factors']} tényező "
        f"kalibrálva valós adattal (ebből {cov.get('n_manual', 0)} kézi forrásból), "
        f"{cov['n_real_sources']} automatizált forrás. ({cov['automation']})"
    )
    lines.append("")
    lines.append("## Legfontosabb pontok")
    lines.append("")
    lines.append(
        f"- A legerősebb hajtóerővel bíró hajtástípus: **{top_dt['label']}** "
        f"({top_dt['dir']}, pontszám {top_dt['score']*100:+.1f} pont)."
    )
    lines.append(
        f"- Legerősebb nyertes szegmens: **{top_winner['label']}** "
        f"({top_winner['dir']}, {top_winner['score']*100:+.1f} pont)."
    )
    lines.append(
        f"- Üzemanyagár (HU): benzin {real['uzemanyagar']['benzin_last']} Ft/l, "
        f"dízel {real['uzemanyagar']['dizel_last']} Ft/l ({real['uzemanyagar']['last_week']} állapot)."
    )
    lines.append(
        f"- Jegybanki alapkamat: {real['makro']['alapkamat_last']}% "
        f"({real['makro']['alapkamat_date']} óta hatályos)."
    )
    lines.append(
        f"- Nyilvános töltőpontok (AC+DC): {int(real['toltoinfra']['ac_last'] + real['toltoinfra']['dc_last']):,} db "
        f"({real['toltoinfra']['last_quarter']})."
    )
    lines.append(
        f"- Forgalomba helyezés: {real['forgalomba']['total_last']:,} db "
        f"({real['forgalomba']['last_quarter']}, YoY {real['forgalomba']['total_yoy']:+.1f}%)."
    )
    lines.append(
        f"- Fogyasztói vásárlási szándék: {real['szentiment']['mp_last']:+.1f} pont "
        f"({real['szentiment']['last_month']})."
    )
    lines.append("")
    lines.append("## Részletek")
    lines.append("")
    lines.append(
        "A teljes forgatókönyv-elemzés, szegmensmátrix és minden valós adatforrás "
        "trendje a `reports/` mappa többi fájljában és a publikált dashboardban "
        "érhető el (`dashboard/dashboard.html`, frissítéshez kérd meg Claude-ot: "
        "\"frissítsd a dashboardot\")."
    )
    lines.append("")

    notification_text = (
        f"{top_dt['label']}: {top_dt['dir']} ({top_dt['score']*100:+.1f} pont). "
        f"Alapkamat {real['makro']['alapkamat_last']}%, benzin {real['uzemanyagar']['benzin_last']} Ft/l. "
        f"Részletek: reports/DIGEST.md"
    )

    return "\n".join(lines), notification_text


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    markdown, notification_text = build_digest()
    OUT_PATH.write_text(markdown, encoding="utf-8")
    print(notification_text)


if __name__ == "__main__":
    main()
