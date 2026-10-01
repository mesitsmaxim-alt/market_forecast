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

FONTOS: az export napját írd a data/raw_eafo/export_date.txt fájlba (ÉÉÉÉ-HH-NN).
Az EAFO a folyamatban lévő negyedévet / évet is kiexportálja, addigi (hiányos)
adattal - pl. a 2026-09-14-i exportban a 2026 Q3 még csak félnegyedév volt, és
-10,75%-os "csökkenést" mutatott. Az import ezért eldobja azokat a negyedéveket
és éveket, amelyek az export napján még nem értek véget. A fájlok módosítási
ideje NEM megbízható export-dátum (pl. git-műveletek átírják) - csak tartalék.

Használat (a kézi export után):
    python3 import_eafo_charging.py
Kimenet:
    data/toltoinfra.json
"""

from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

RAW_DIR = Path(__file__).parent / "data" / "raw_eafo"
EXPORT_DATE_PATH = RAW_DIR / "export_date.txt"
OUT_PATH = Path(__file__).parent / "data" / "toltoinfra.json"


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def export_date() -> tuple[datetime.date, str]:
    """Az EAFO-export napja: az export_date.txt-ből, ennek híján (kevésbé
    megbízhatóan) a negyedéves CSV módosítási idejéből."""
    if EXPORT_DATE_PATH.exists():
        return datetime.date.fromisoformat(EXPORT_DATE_PATH.read_text().strip()), "export_date.txt"
    mtime = (RAW_DIR / "ac_dc_counts_quarterly.csv").stat().st_mtime
    return datetime.date.fromtimestamp(mtime), "a CSV módosítási ideje (tartalék)"


def quarter_end(label: str) -> datetime.date:
    """'2026 Q3' -> 2026-09-30"""
    year, q = label.split()
    month = int(q[1]) * 3
    nxt = datetime.date(int(year) + (month == 12), month % 12 + 1, 1)
    return nxt - datetime.timedelta(days=1)


EXPORTED_ON, EXPORT_DATE_SOURCE = export_date()
DROPPED: list[str] = []


def complete_quarter(label: str) -> bool:
    if quarter_end(label) > EXPORTED_ON:
        DROPPED.append(label)
        return False
    return True


def parse_quarterly_counts():
    rows = read_csv(RAW_DIR / "ac_dc_counts_quarterly.csv")
    quarters, ac, dc = [], [], []
    for row in rows:
        if not row["AC"] or not row["DC"]:
            continue  # jövőbeli, még üres negyedév
        if not complete_quarter(row["Category"]):
            continue  # az export napján még folyamatban lévő (hiányos) negyedév
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
        if quarter_end(row["Category"]) > EXPORTED_ON:
            continue
        quarters.append(row["Category"])
        ac_pct.append(float(row["AC"]))
        dc_pct.append(float(row["DC"]))
    return {"quarters": quarters, "ac_pct": ac_pct, "dc_pct": dc_pct}


def parse_power_breakdown(filename: str):
    # az export évében még folyamatban lévő év hiányos -> kimarad
    rows = [row for row in read_csv(RAW_DIR / filename)
            if datetime.date(int(row["Category"]), 12, 31) <= EXPORTED_ON]
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
        "export_date": EXPORTED_ON.isoformat(),
        "export_date_source": EXPORT_DATE_SOURCE,
        "quarterly_counts": parse_quarterly_counts(),
        "quarterly_yoy": parse_quarterly_yoy(),
        "ac_by_power_yearly": parse_power_breakdown("ac_by_power_yearly.csv"),
        "dc_by_power_yearly": parse_power_breakdown("dc_by_power_yearly.csv"),
    }
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    data["dropped_incomplete_quarters"] = sorted(set(DROPPED))
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n = len(data["quarterly_counts"]["quarters"])
    print(f"Elmentve: {OUT_PATH} ({n} negyedéves adatpont, export: {EXPORTED_ON}; "
          f"hiányos negyedév kihagyva: {', '.join(data['dropped_incomplete_quarters']) or 'nincs'})")


if __name__ == "__main__":
    main()
