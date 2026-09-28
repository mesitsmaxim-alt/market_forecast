#!/usr/bin/env python3
"""
Eurostat fogyasztói szentiment-adat letöltése Magyarországra: "tartós
fogyasztási cikk vásárlási szándék a következő 12 hónapban" (autópiaci
proxy) és az általános fogyasztói bizalmi index.

Forrás: Eurostat ei_bsco_m (Business and Consumer Survey), publikus REST
API, autentikáció nélkül.
    https://ec.europa.eu/eurostat/databrowser/view/EI_BSCO_M

Ez az egyetlen forrás a projektben, ami valódi ELŐRETEKINTŐ indikátor: nem
azt méri, mi történt (mint az állomány/forgalomba helyezés/árfolyam-adatok),
hanem hogy az emberek mit terveznek a következő 12 hónapban.

Használat:
    python3 fetchers/fetch_szentiment.py
Kimenet:
    data/szentiment.json
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

API_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "ei_bsco_m?format=JSON&geo=HU&indic=BS-MP-NY&indic=BS-CSMCI&s_adj=SA&lang=en"
)
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_PATH = DATA_DIR / "_raw_szentiment.json"
OUT_PATH = DATA_DIR / "szentiment.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def download():
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(["curl", "-sL", "-o", str(RAW_PATH), API_URL, "-A", UA], check=True)


def parse():
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))

    # Ellenőrizzük, hogy a dimenziók valóban a várt sorrendben és méretben
    # vannak (freq, s_adj, unit, geo mind egyelemű a lekérdezés miatt) -
    # enélkül a lapos value-tömb indexelése hibás lenne.
    assert raw["id"] == ["freq", "indic", "s_adj", "unit", "geo", "time"], raw["id"]
    n_indic = raw["size"][1]
    n_time = raw["size"][5]
    assert raw["size"][0] == 1 and raw["size"][2:5] == [1, 1, 1], raw["size"]

    indic_index = raw["dimension"]["indic"]["category"]["index"]
    times = list(raw["dimension"]["time"]["category"]["index"].keys())
    values = raw["value"]

    def series_for(indic_code: str) -> list[float | None]:
        i = indic_index[indic_code]
        return [values.get(str(i * n_time + t)) for t in range(n_time)]

    major_purchases = series_for("BS-MP-NY")
    consumer_confidence = series_for("BS-CSMCI")

    # levágjuk a végéről a hiányzó (még be nem érkezett) hónapokat
    last_valid = n_time
    while last_valid > 0 and (
        major_purchases[last_valid - 1] is None or consumer_confidence[last_valid - 1] is None
    ):
        last_valid -= 1

    return {
        "source": API_URL,
        "unit": "balance (%), szezonálisan igazítva",
        "months": times[:last_valid],
        "major_purchases_intention": major_purchases[:last_valid],
        "consumer_confidence": consumer_confidence[:last_valid],
    }


def main():
    download()
    data = parse()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Elmentve: {OUT_PATH} ({len(data['months'])} hónap, utolsó: {data['months'][-1]})")


if __name__ == "__main__":
    main()
