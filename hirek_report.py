#!/usr/bin/env python3
"""
Piaci hírek riport a fetchers/fetch_hirek.py által gyűjtött cikkekből.

Előfeltétel: futtasd előbb a fetchers/fetch_hirek.py-t.

Használat:
    python3 hirek_report.py
Kimenet:
    reports/hirek_riport_<dátum>.md
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "hirek.json"
REPORTS_DIR = Path(__file__).parent / "reports"


def build_report() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    articles = data["articles"]

    lines = []
    lines.append(f"# Piaci hírek riport — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(
        f"{len(articles)} releváns cikk, hazai autós és gazdasági portálok RSS-feedjéből "
        "(kulcsszó-alapú piaci relevancia-szűréssel, ld. fetchers/fetch_hirek.py)."
    )
    lines.append("")

    by_source = defaultdict(list)
    for a in articles:
        by_source[a["source"]].append(a)

    for source, items in by_source.items():
        lines.append(f"## {source}")
        lines.append("")
        for a in items:
            date_label = (a["published"] or "")[:10]
            lines.append(f"- [{a['title']}]({a['link']}) — {date_label}")
        lines.append("")

    return "\n".join(lines)


def main():
    REPORTS_DIR.mkdir(exist_ok=True)
    if not DATA_PATH.exists():
        print("Nincs data/hirek.json — futtasd előbb: python3 fetchers/fetch_hirek.py")
        return
    content = build_report()
    out_path = REPORTS_DIR / f"hirek_riport_{dt.date.today().isoformat()}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
