#!/usr/bin/env python3
"""
Élő (napi frissülő) magyar üzemanyagár letöltése a holtankoljak.hu-ról.

Ez a KSH régiós üzemanyagár-táblával (fetchers/fetch_uzemanyagar.py) szemben
NEM egy befagyott, egyszeri kiadvány-pillanatkép, hanem minden futáskor a
TÉNYLEGES, aktuális napi/heti országos átlagárat adja vissza - ezért ez a
forrás hajtja az oil_price tényező kalibrációját (calibrate_factors.py).

A holtankoljak.hu oldal minden hétköznap frissül, és a táblázata a jelenlegi
hét mellett ~1 hónapos és ~1 éves visszatekintést is ad - így a YoY trend
egyetlen lekérésből számolható, nem kell hosszú saját idősort gyűjteni.

Forrás: https://holtankoljak.hu/uzemanyag_arvaltozasok

Használat:
    python3 fetchers/fetch_uzemanyag_elo.py
Kimenet:
    data/uzemanyagar_elo.json
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

SOURCE_URL = "https://holtankoljak.hu/uzemanyag_arvaltozasok"
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_PATH = DATA_DIR / "_raw_uzemanyag_elo.html"
OUT_PATH = DATA_DIR / "uzemanyagar_elo.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def download():
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(["curl", "-sL", "-o", str(RAW_PATH), SOURCE_URL, "-A", UA], check=True)


def parse():
    soup = BeautifulSoup(RAW_PATH.read_text(encoding="utf-8"), "html.parser")
    full_text = soup.get_text(" ", strip=True)

    # fejléc-dátum: "Üzemanyagár-változás – 2026. szeptember 14."
    date_m = re.search(r"Üzemanyagár-változás\s*[–-]\s*(\d{4}\.\s*\S+\s*\d{1,2}\.)", full_text)
    headline_date = date_m.group(1).strip() if date_m else None

    # mai országos átlag: "95-ös benzin: 626 Ft/liter" / "Gázolaj: 701 Ft/liter"
    benzin_m = re.search(r"95-ös benzin:\s*(\d+)\s*Ft", full_text)
    dizel_m = re.search(r"[GgÁáA]ázolaj:\s*(\d+)\s*Ft", full_text)
    headline = {
        "benzin_95": int(benzin_m.group(1)) if benzin_m else None,
        "gazolaj": int(dizel_m.group(1)) if dizel_m else None,
    }

    # táblázat: 95-ös Benzin E10 / Gázolaj stb., 3 időszak (jelen hét, ~1 hónapja, ~1 éve)
    table = soup.find("table")
    rows = [[c.get_text(strip=True) for c in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]
    header = rows[0]
    periods = header[1:]  # 3 dátumtartomány-felirat

    def to_int(cell):
        m = re.search(r"\d+", cell)
        return int(m.group()) if m else None

    fuels = {}
    for row in rows[1:]:
        if len(row) < 2:
            continue
        name = row[0]
        values = [to_int(c) for c in row[1:]]
        fuels[name] = dict(zip(periods, values))

    return {
        "source": SOURCE_URL,
        "headline_date": headline_date,
        "headline": headline,
        "periods": periods,
        "fuels": fuels,
    }


def main():
    download()
    data = parse()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Elmentve: {OUT_PATH} ({data['headline_date']}: "
        f"benzin {data['headline']['benzin_95']} Ft/l, gázolaj {data['headline']['gazolaj']} Ft/l)"
    )


if __name__ == "__main__":
    main()
