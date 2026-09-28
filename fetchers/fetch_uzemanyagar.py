#!/usr/bin/env python3
"""
KSH régiós üzemanyagár-összehasonlítás letöltése és feldolgozása.

Forrás: https://www.ksh.hu/s/kiserleti-statisztika/kiadvanyok/regios-uzemanyagarak-osszehasonlitasa/
(alapadat: EU Weekly Oil Bulletin) — heti átlagár Ft/literben, Magyarország +
9 régiós ország, 95-ös benzin és dízel.

Megjegyzés: ez egy adott kiadványhoz tartozó táblamelléklet, nem folyamatosan
frissülő live API — időről időre új linkkel jelenik meg új kiadás. Ha nincs
frissebb elérhető, ez a szkript a legutóbb ismert táblát dolgozza fel; a
tényleges "friss" napi árhoz a holtankoljak.hu / benzinkutarak.hu forrásokat
érdemes később bekötni (ld. README).

Használat:
    python3 fetchers/fetch_uzemanyagar.py
Kimenet:
    data/uzemanyagar.json
"""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path

import openpyxl

SOURCE_URL = (
    "https://www.ksh.hu/s/kiserleti-statisztika/kiadvanyok/"
    "regios-uzemanyagarak-osszehasonlitasa/tablamelleklet.xlsx"
)
SOURCE_PAGE = (
    "https://www.ksh.hu/s/kiserleti-statisztika/kiadvanyok/"
    "regios-uzemanyagarak-osszehasonlitasa/"
)
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_PATH = DATA_DIR / "_raw_uzemanyagar.xlsx"
OUT_PATH = DATA_DIR / "uzemanyagar.json"

SHEETS = {"BENZIN_országok": "benzin", "Dízel_országok": "dizel"}


def download():
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(
        [
            "curl", "-sL", "-o", str(RAW_PATH), SOURCE_URL,
            "-A", (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "-H", f"Referer: {SOURCE_PAGE}",
            "-H", "Accept-Language: hu-HU,hu;q=0.9",
        ],
        check=True,
    )


def parse_sheet(ws):
    rows = list(ws.iter_rows(values_only=True))
    countries = [c for c in rows[1][1:] if c is not None]
    weeks = []
    by_country = {c: [] for c in countries}
    for row in rows[2:]:
        date = row[0]
        if not isinstance(date, datetime.datetime):
            continue
        weeks.append(date.date().isoformat())
        for country, value in zip(countries, row[1 : 1 + len(countries)]):
            by_country[country].append(value)
    # növekvő időrendbe rendezés (a forrásban csökkenő dátumsorrend van)
    order = sorted(range(len(weeks)), key=lambda i: weeks[i])
    weeks_sorted = [weeks[i] for i in order]
    by_country_sorted = {c: [v[i] for i in order] for c, v in by_country.items()}
    return weeks_sorted, by_country_sorted


def parse():
    wb = openpyxl.load_workbook(RAW_PATH, data_only=True)
    result = {"source": SOURCE_URL, "source_page": SOURCE_PAGE, "unit": "Ft/liter"}
    for sheet_name, key in SHEETS.items():
        weeks, by_country = parse_sheet(wb[sheet_name])
        result[key] = {"weeks": weeks, "prices": by_country}
    return result


def main():
    download()
    data = parse()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n_weeks = len(data["benzin"]["weeks"])
    print(f"Elmentve: {OUT_PATH} ({n_weeks} heti adatpont)")


if __name__ == "__main__":
    main()
