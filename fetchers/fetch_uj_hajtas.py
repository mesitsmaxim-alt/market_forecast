#!/usr/bin/env python3
"""
Új személyautók forgalomba helyezése hajtásenergia szerint, Magyarországra.

Forrás: Eurostat road_eqr_carpda ("New passenger cars by type of motor
energy"), publikus REST API, autentikáció nélkül, éves adat.
    https://ec.europa.eu/eurostat/databrowser/view/road_eqr_carpda

Ez az egyetlen gépileg elérhető forrás, ami az ÚJ autók piacát hajtás szerint
bontja (a KSH STADAT tábláiban csak járműnem / gyártmány szerinti bontás van),
és a plug-in hibridet külön választja a nem tölthető hibridtől. Az engine
hajtástípus-momentuma ebből számol (a részesedés változása az új autókon
belül), nem a teljes állomány növekedéséből - az utóbbi kis bázisú
kategóriáknál (pl. elektromos) bázishatást mér, nem keresletet.

A kategóriák az Eurostatban egymásba ágyazottak (PET = PET_X_HYB +
ELC_PET_HYB + ELC_PET_PI, ugyanígy DIE), ezért a "kizárólagos" kategóriákat
adjuk össze:
    ICE  = PET_X_HYB + DIE_X_HYB          (tisztán belső égésű)
    HEV  = ELC_PET_HYB + ELC_DIE_HYB      (nem tölthető hibrid - az Eurostat
                                           ide sorolja a mild hibrideket is)
    PHEV = ELC_PET_PI + ELC_DIE_PI
    BEV  = ELC
    egyeb = TOTAL - a fentiek (gáz, LPG, hidrogén, egyéb)

Használat:
    python3 fetchers/fetch_uj_hajtas.py
Kimenet:
    data/uj_hajtas.json
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

API_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "road_eqr_carpda?format=JSON&lang=EN&geo=HU&unit=NR"
)
SOURCE_PAGE = "https://ec.europa.eu/eurostat/databrowser/view/road_eqr_carpda"
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_PATH = DATA_DIR / "_raw_uj_hajtas.json"
OUT_PATH = DATA_DIR / "uj_hajtas.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# A dashboard megoszlás-diagramjához a KSH-állománnyal azonos kategóriák
# (benzin / dízel külön, a hibrid a HEV+PHEV együtt - mert a KSH-állomány sem
# bontja szét), hogy a két diagram közvetlenül összevethető legyen.
DETAIL = {
    "benzin": ["PET_X_HYB"],
    "dizel": ["DIE_X_HYB"],
    "hibrid": ["ELC_PET_HYB", "ELC_DIE_HYB", "ELC_PET_PI", "ELC_DIE_PI"],
    "elektromos": ["ELC"],
}

GROUPS = {
    "ICE": ["PET_X_HYB", "DIE_X_HYB"],
    "HEV": ["ELC_PET_HYB", "ELC_DIE_HYB"],
    "PHEV": ["ELC_PET_PI", "ELC_DIE_PI"],
    "BEV": ["ELC"],
}


def download():
    DATA_DIR.mkdir(exist_ok=True)
    subprocess.run(["curl", "-sL", "-o", str(RAW_PATH), API_URL, "-A", UA], check=True)


def parse() -> dict:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    # a lapos value-tömb indexelése csak a várt dimenzió-sorrenddel helyes
    assert raw["id"] == ["freq", "unit", "mot_nrg", "geo", "time"], raw["id"]
    assert raw["size"][0] == 1 and raw["size"][1] == 1 and raw["size"][3] == 1, raw["size"]

    nrg_index = raw["dimension"]["mot_nrg"]["category"]["index"]
    time_index = raw["dimension"]["time"]["category"]["index"]
    n_time = raw["size"][4]
    values = raw["value"]

    def get(code: str, year: str):
        if code not in nrg_index:
            return None
        return values.get(str(nrg_index[code] * n_time + time_index[year]))

    years, counts = [], {k: [] for k in [*GROUPS, "egyeb", "total"]}
    detail = {k: [] for k in [*DETAIL, "egyeb"]}
    for year in sorted(time_index, key=time_index.get):
        total = get("TOTAL", year)
        parts = {g: [get(c, year) for c in codes] for g, codes in GROUPS.items()}
        # csak teljes évet veszünk fel (egy hiányzó kategória torzítaná a részesedést)
        if not total or any(v is None for vals in parts.values() for v in vals):
            continue
        years.append(int(year))
        sums = {g: sum(vals) for g, vals in parts.items()}
        for g, v in sums.items():
            counts[g].append(v)
        counts["egyeb"].append(total - sum(sums.values()))
        counts["total"].append(total)
        dsum = {k: sum(get(c, year) for c in codes) for k, codes in DETAIL.items()}
        for k, v in dsum.items():
            detail[k].append(round(v / total * 100, 2))
        detail["egyeb"].append(round((total - sum(dsum.values())) / total * 100, 2))

    shares = {
        g: [round(c / t * 100, 2) for c, t in zip(counts[g], counts["total"])]
        for g in [*GROUPS, "egyeb"]
    }
    return {
        "source": "Eurostat road_eqr_carpda — új személyautók hajtásenergia szerint (HU)",
        "source_page": SOURCE_PAGE,
        "note": "A HEV az Eurostat 'hybrid electric' kategóriája, a mild hibrideket is tartalmazza.",
        "years": years,
        "counts": counts,
        "shares_pct": shares,
        # a KSH-állomány kategóriáival azonos bontás (dashboard-diagramhoz)
        "detail_shares_pct": detail,
    }


def main():
    download()
    data = parse()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    last = data["years"][-1]
    sh = {g: v[-1] for g, v in data["shares_pct"].items()}
    print(f"Elmentve: {OUT_PATH} ({data['years'][0]}–{last}, {last}: "
          f"ICE {sh['ICE']}%, HEV {sh['HEV']}%, PHEV {sh['PHEV']}%, BEV {sh['BEV']}%)")


if __name__ == "__main__":
    main()
