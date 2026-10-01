#!/usr/bin/env python3
"""
Üzemanyagár-változás hosszú idősora Magyarországra: az Eurostat harmonizált
fogyasztói árindexének (HICP) "Üzemanyagok és kenőanyagok személyszállító
járművekhez" tétele (COICOP CP0722), havi 12 havi változás (%).

Forrás: Eurostat prc_hicp_manr, publikus REST API, autentikáció nélkül.
    https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_manr

Mire kell: az élő kútár (holtankoljak.hu) csak a mai, az 1 hónapos és az 1
éves árat adja - a calibrate_factors.py oil_price tényezőjének forgatókönyv-
sávjához (a 12 havi változások történeti ingadozása) és a backtest.py
üzemanyagár-tesztjéhez (2003-tól) hosszú idősor kell. A KSH régiós táblája
(fetch_uzemanyagar.py) csak 2023-tól ad heti adatot.

Használat:
    python3 fetchers/fetch_uzemanyag_index.py
Kimenet:
    data/uzemanyag_index.json
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

API_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "prc_hicp_manr?format=JSON&lang=EN&geo=HU&coicop=CP0722"
)
SOURCE_PAGE = "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_manr"
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_PATH = DATA_DIR / "_raw_uzemanyag_index.json"
OUT_PATH = DATA_DIR / "uzemanyag_index.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def download():
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(["curl", "-sL", "-o", str(RAW_PATH), API_URL, "-A", UA], check=True)


def parse() -> dict:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    assert raw["id"] == ["freq", "unit", "coicop", "geo", "time"], raw["id"]
    assert raw["size"][:4] == [1, 1, 1, 1], raw["size"]
    time_index = raw["dimension"]["time"]["category"]["index"]
    values = raw["value"]

    months, rates = [], []
    for month in sorted(time_index, key=time_index.get):
        v = values.get(str(time_index[month]))
        if v is not None:
            months.append(month)
            rates.append(v)

    # éves átlagos változás: a havi 12 havi változások átlaga, csak teljes évre
    by_year: dict[int, list[float]] = {}
    for m, v in zip(months, rates):
        by_year.setdefault(int(m[:4]), []).append(v)
    years = sorted(y for y, vals in by_year.items() if len(vals) == 12)

    return {
        "source": "Eurostat prc_hicp_manr — HICP, üzemanyagok (CP0722), HU, 12 havi változás",
        "source_page": SOURCE_PAGE,
        "unit": "% (az előző év azonos hónapjához képest)",
        "months": months,
        "yoy_pct": rates,
        "annual_years": years,
        "annual_avg_yoy_pct": [round(sum(by_year[y]) / 12, 2) for y in years],
    }


def main():
    download()
    data = parse()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Elmentve: {OUT_PATH} ({data['months'][0]}–{data['months'][-1]}, "
          f"{len(data['months'])} hónap, {len(data['annual_years'])} teljes év)")


if __name__ == "__main__":
    main()
