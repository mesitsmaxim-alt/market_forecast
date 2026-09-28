#!/usr/bin/env python3
"""
KSH STADAT 24.1.1.25 (sza0025) letöltése és feldolgozása:
személygépkocsi-állomány gyártmány és üzemanyag-felhasználás szerint, 2002-től.

Forrás: https://www.ksh.hu/stadat_files/sza/hu/sza0025.html
Ez a "2. lépés" (szegmentált riportolás) fő adatforrása: valós márka- és
hajtástípus-szintű állományadat, amiből trend (YoY, több éves CAGR) számolható.

Használat:
    python3 fetchers/fetch_jarmuallomany.py
Kimenet:
    data/jarmuallomany.json
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import openpyxl

SOURCE_URL = "https://www.ksh.hu/stadat_files/sza/hu/sza0025.xlsx"
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_PATH = DATA_DIR / "_raw_sza0025.xlsx"
OUT_PATH = DATA_DIR / "jarmuallomany.json"

FUEL_TYPE_LABELS = {
    "benzinüzemű": "benzin",
    "dízelüzemű": "dizel",
    "hibridüzemű": "hibrid",
    "elektromos üzemű": "elektromos",
    "egyéb üzemű": "egyeb",
}

# A KSH táblában a márkalista és az "Ebből:" hajtástípus-bontás között van
# egy üres "Ebből: " elválasztó sor; ez a segéd ez alapján dönt.
SEPARATOR_LABEL = "Ebből:"
TOTAL_LABEL = "Összesen"


def download():
    # A rendszer Python (python.org build) nem látja a macOS keychain
    # tanúsítványait -> urllib SSL hibát dob. A curl a rendszer trust store-t
    # használja, ezért azzal töltjük le (ugyanaz működött kézi teszten is).
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(
        [
            "curl", "-sL", "-o", str(RAW_PATH), SOURCE_URL,
            "-A", (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "-H", "Referer: https://www.ksh.hu/stadat_files/sza/hu/sza0025.html",
            "-H", "Accept-Language: hu-HU,hu;q=0.9",
        ],
        check=True,
    )


def parse():
    wb = openpyxl.load_workbook(RAW_PATH, data_only=True)
    sheet_name = next(n for n in wb.sheetnames if n != "Információk")
    ws = wb[sheet_name]

    rows = list(ws.iter_rows(values_only=True))
    header_row = rows[1]
    years = [int(y) for y in header_row[1:] if y is not None]

    # A táblában két "Ebből: " elválasztó sor is szerepel (egy a márkalista,
    # egy a hajtástípus-bontás előtt) - ezeket egyszerűen kihagyjuk, és a
    # hajtástípus-sorokat a nevük alapján, nem a pozíciójuk alapján ismerjük fel.
    total = None
    brands: dict[str, list] = {}
    fuel_types: dict[str, list] = {}

    for row in rows[2:]:
        label = row[0]
        if label is None:
            continue
        if isinstance(label, str) and label.strip().startswith(SEPARATOR_LABEL):
            continue
        values = list(row[1 : 1 + len(years)])
        if label == TOTAL_LABEL:
            total = values
        elif label in FUEL_TYPE_LABELS:
            fuel_types[FUEL_TYPE_LABELS[label]] = values
        else:
            brands[label] = values

    return {
        "source": SOURCE_URL,
        "source_page": "https://www.ksh.hu/stadat_files/sza/hu/sza0025.html",
        "years": years,
        "total": total,
        "brands": brands,
        "fuel_types": fuel_types,
    }


def main():
    download()
    data = parse()
    OUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Elmentve: {OUT_PATH} ({len(data['years'])} év, {len(data['brands'])} márka)")


if __name__ == "__main__":
    main()
