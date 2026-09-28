#!/usr/bin/env python3
"""
MNB makróadatok letöltése és feldolgozása: jegybanki alapkamat idősor és
havi átlagos EUR/HUF árfolyam.

Források:
    https://www.mnb.hu/root/BaseRate/BaseRateExcel/alapkamat.xlsx
    https://statisztika.mnb.hu/timeseries/hu0301_arfolyam.xls (havi átlag munkalap, EUR oszlop)

Használat:
    python3 fetchers/fetch_makro.py
Kimenet:
    data/makro.json
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import openpyxl
import xlrd

DATA_DIR = Path(__file__).parent.parent / "data"
RATE_URL = "https://www.mnb.hu/root/BaseRate/BaseRateExcel/alapkamat.xlsx"
FX_URL = "https://statisztika.mnb.hu/timeseries/hu0301_arfolyam.xls"
RATE_RAW = DATA_DIR / "_raw_alapkamat.xlsx"
FX_RAW = DATA_DIR / "_raw_arfolyam.xls"
OUT_PATH = DATA_DIR / "makro.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def download(url: str, dest: Path):
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(
        ["curl", "-sL", "-o", str(dest), url, "-A", UA, "-H", "Referer: https://www.mnb.hu/"],
        check=True,
    )


def parse_base_rate() -> dict:
    wb = openpyxl.load_workbook(RATE_RAW, data_only=True)
    ws = wb["Alapkamat"]
    rows = list(ws.iter_rows(values_only=True))[1:]  # fejléc nélkül
    dates, values = [], []
    for date, pct_str in rows:
        if date is None or pct_str is None:
            continue
        dates.append(date.date().isoformat())
        values.append(float(str(pct_str).replace("%", "").replace(",", ".")))
    # a forrás csökkenő időrendben van -> növekvőre fordítjuk
    dates.reverse()
    values.reverse()
    return {"dates": dates, "values": values, "unit": "%"}


def parse_eur_huf() -> dict:
    wb = xlrd.open_workbook(FX_RAW)
    ws = wb.sheet_by_name("havi átlag")
    header = [ws.cell_value(3, c) for c in range(ws.ncols)]
    eur_col = header.index("EUR")

    months, values = [], []
    for r in range(5, ws.nrows):
        label = ws.cell_value(r, 0)
        value = ws.cell_value(r, eur_col)
        # Csak "ÉÉÉÉ. hónap" címkéjű adatsorok: a táblázat tetején van egy
        # "Egység" sor (értéke 1 = egységszorzó), ami korábban adatpontként
        # került be az idősor elejére, és elrontotta a görbét és a trendet.
        if not label or value in ("", None) or not re.match(r"^\d{4}\.", str(label)):
            continue
        months.append(label)
        values.append(float(value))
    return {"months": months, "values": values, "unit": "HUF/EUR (havi átlag)"}


def main():
    download(RATE_URL, RATE_RAW)
    download(FX_URL, FX_RAW)

    data = {
        "alapkamat": {"source": RATE_URL, **parse_base_rate()},
        "eur_huf_havi": {"source": FX_URL, **parse_eur_huf()},
    }
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Elmentve: {OUT_PATH} "
        f"(alapkamat: {len(data['alapkamat']['dates'])} rekord, "
        f"EUR/HUF: {len(data['eur_huf_havi']['months'])} hónap)"
    )


if __name__ == "__main__":
    main()
