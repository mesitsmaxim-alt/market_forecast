#!/usr/bin/env python3
"""
EAFO (European Alternative Fuels Observatory) töltőinfrastruktúra-adat
importálása Magyarországra.

Az EAFO dashboard JS-alapú (nincs egyszerű publikus API/letöltés), ezért ez
NEM automata fetcher: a CSV-ket kézzel kell exportálni a grafikonok "Download
CSV" gombjával az alábbi oldalról, és a data/raw_eafo/ mappába másolni:

    https://alternative-fuels-observatory.ec.europa.eu/transport-mode/road/hungary/infrastructure

Szükséges fájlok (a grafikon "Download CSV" exportjai, ezekkel a nevekkel):
    data/raw_eafo/ac_dc_counts_quarterly.csv   - AC/DC töltőpontszám negyedévente
    data/raw_eafo/ac_dc_yoy_quarterly.csv      - AC/DC növekedés %, negyedévente (YoY)
    data/raw_eafo/ac_by_power_yearly.csv       - AC töltők teljesítmény-kategória szerint, évente
    data/raw_eafo/dc_by_power_yearly.csv       - DC töltők teljesítmény-kategória szerint, évente

Használat (a kézi export után):
    python3 import_eafo_charging.py
Kimenet:
    data/toltoinfra.json
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

RAW_DIR = Path(__file__).parent / "data" / "raw_eafo"
OUT_PATH = Path(__file__).parent / "data" / "toltoinfra.json"


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_quarterly_counts():
    rows = read_csv(RAW_DIR / "ac_dc_counts_quarterly.csv")
    quarters, ac, dc = [], [], []
    for row in rows:
        if not row["AC"] or not row["DC"]:
            continue  # jövőbeli, még üres negyedév
        quarters.append(row["Category"])
        ac.append(float(row["AC"]))
        dc.append(float(row["DC"]))
    return {"quarters": quarters, "ac": ac, "dc": dc}


def parse_quarterly_yoy():
    rows = read_csv(RAW_DIR / "ac_dc_yoy_quarterly.csv")
    quarters, ac_pct, dc_pct = [], [], []
    for row in rows:
        if not row["AC"] or not row["DC"]:
            continue
        quarters.append(row["Category"])
        ac_pct.append(float(row["AC"]))
        dc_pct.append(float(row["DC"]))
    return {"quarters": quarters, "ac_pct": ac_pct, "dc_pct": dc_pct}


def parse_power_breakdown(filename: str):
    rows = read_csv(RAW_DIR / filename)
    years = [row["Category"] for row in rows]
    categories = [k for k in rows[0].keys() if k != "Category"]
    series = {cat: [float(row[cat]) for row in rows] for cat in categories}
    return {"years": years, "series": series}


def main():
    data = {
        "source_page": (
            "https://alternative-fuels-observatory.ec.europa.eu/"
            "transport-mode/road/hungary/infrastructure"
        ),
        "note": (
            "Kézzel exportált CSV-k az EAFO dashboardról (nincs publikus API). "
            "Frissítéshez: töltsd le újra a CSV-ket a fenti oldalról, másold a "
            "data/raw_eafo/ mappába, majd futtasd újra ezt a scriptet."
        ),
        "quarterly_counts": parse_quarterly_counts(),
        "quarterly_yoy": parse_quarterly_yoy(),
        "ac_by_power_yearly": parse_power_breakdown("ac_by_power_yearly.csv"),
        "dc_by_power_yearly": parse_power_breakdown("dc_by_power_yearly.csv"),
    }
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n = len(data["quarterly_counts"]["quarters"])
    print(f"Elmentve: {OUT_PATH} ({n} negyedéves adatpont)")


if __name__ == "__main__":
    main()
