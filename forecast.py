"""
Egyszerű trend-előrejelzés a valós adatforrások (KSH/MNB/Eurostat) idősoraira.

Szándékosan sima legkisebb négyzetek (OLS) lineáris regresszió, nincs numpy/ML-
függőség - a projekt többi része is tiszta stdlib (lásd CLAUDE.md). A cél nem egy
pontos statisztikai modell, hanem a jelenlegi trend irányának és nagyságrendjének
becslése a dashboard "Előrejelzés" füléhez, jelölt bizonytalansági sávval.

A szegmens-pontszámokhoz (engine.py) NEM ez a modul ad előrejelzést - ott a
meglévő pesszimista/alap/optimista forgatókönyv-sáv szolgál explicit, forgatókönyv-
alapú előrejelzésként, hogy ne legyen két egymásnak ellentmondó predikciós logika.
"""

from __future__ import annotations

import math


def linreg_forecast(y: list[float], steps: int) -> dict | None:
    """OLS egyenes illesztése y-ra (x = 0..n-1), és `steps` pontos extrapoláció.

    Visszaadja: {"forecast": [...], "lower": [...], "upper": [...], "slope": float}
    A lower/upper a reziduálok szórásából számolt +-1 std sáv (nem szigorú
    statisztikai konfidenciaintervallum, csak durva bizonytalanság-jelzés).
    Legalább 3 valós adatpont kell, különben None (túl zajos/rövid sorozathoz
    nem érdemes egyenest illeszteni).
    """
    clean = [v for v in y if v is not None]
    n = len(clean)
    if n < 3:
        return None

    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(clean) / n
    num = sum((x - x_mean) * (v - y_mean) for x, v in zip(xs, clean))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return None
    slope = num / den
    intercept = y_mean - slope * x_mean

    residuals = [v - (slope * x + intercept) for x, v in zip(xs, clean)]
    std = math.sqrt(sum(r * r for r in residuals) / n)

    forecast, lower, upper = [], [], []
    for i in range(1, steps + 1):
        x = n - 1 + i
        point = slope * x + intercept
        forecast.append(round(point, 3))
        lower.append(round(point - std, 3))
        upper.append(round(point + std, 3))

    return {"forecast": forecast, "lower": lower, "upper": upper, "slope": round(slope, 4)}


def naive_forecast_card(series: list[float], steps: int, horizon_label: str,
                        band_window: int) -> dict | None:
    """"Változatlan szint + szokásos ingadozás" kártya olyan soroknak, ahol a
    lineáris trendvetítés mintán kívül rosszabb a naiv becslésnél (2026-10-09-i
    walk-forward audit: szentiment MAE 2x, alapkamat 1,6x a random walké).

    A pont az utolsó érték; a h. lépés sávja ± az utolsó `band_window` pontban
    megfigyelt h lépéses változások (populációs) szórása - azaz a horizonttal
    szélesedik, és a sor tényleges ingadozását mutatja, nem egy illesztés
    reziduálját. Közelítőleg ±1 szórásos sáv, ugyanúgy, mint a linreg kártyáé."""
    clean = [v for v in series if v is not None]
    if len(clean) < steps + 3:
        return None
    hist = clean[-(band_window + steps):]
    last = clean[-1]
    points, lower, upper = [], [], []
    for h in range(1, steps + 1):
        changes = [hist[i + h] - hist[i] for i in range(len(hist) - h)]
        std = math.sqrt(sum(c * c for c in changes) / len(changes) - (sum(changes) / len(changes)) ** 2)
        points.append(round(last, 3))
        lower.append(round(last - std, 3))
        upper.append(round(last + std, 3))
    return {
        "kind": "naive",
        "horizon_label": horizon_label,
        "points": points,
        "lower": lower,
        "upper": upper,
        "slope": 0.0,
    }


MIN_OOS_ERRORS = 3


def oos_band(series: list[float], steps: int, window: int) -> list[float] | None:
    """A h. lépés sávfélszélessége: ugyanezzel az ablakkal a múltban készült
    vetítések h lépéses, mintán kívüli hibáinak RMS-e (a torzítást is
    tartalmazza, nem csak a szórást).

    A reziduál-szórás csak az illesztés zaját méri, ezért a 2026-10-09-i
    walk-forward auditon a lineáris kártyák ±1 sávja a valós kimenetelek
    0-18%-át fedte le (a névleges ~68% helyett). Gyorsuló soroknál (hibrid,
    elektromos részesedés) ez a sáv is szűkebb a valós hibánál, mert a
    lineáris trend tartósan alulbecsül. None, ha valamelyik lépéshez
    MIN_OOS_ERRORS-nál kevesebb hiba van."""
    errors = [[] for _ in range(steps)]
    for cut in range(window, len(series)):
        fc = linreg_forecast(series[cut - window:cut], steps)
        if fc is None:
            continue
        for h in range(steps):
            if cut + h < len(series):
                errors[h].append(series[cut + h] - fc["forecast"][h])
    if any(len(e) < MIN_OOS_ERRORS for e in errors):
        return None
    return [math.sqrt(sum(x * x for x in e) / len(e)) for e in errors]


def forecast_card(series: list[float], steps: int, horizon_label: str,
                  window: int | None = None) -> dict | None:
    """linreg_forecast() eredményét a dashboard-kártyákhoz illő alakra hozza.

    `window`: csak az utolsó ennyi (nem None) adatpontra illesztünk egyenest.
    A teljes, évtizedes idősorra illesztett egyenes félrevezető (pl. az
    alapkamatnál a 90-es évek 20% feletti szintje negatív kamatot "jósolt",
    a gyorsuló hibrid/elektromos részesedésnél a jelenleginél kisebbet) - a
    cél a JELENLEGI trend iránya, ezért a friss ablak a helyes alap. A
    megjelenített történeti görbe ettől még a teljes idősor marad.

    A sáv oos_band()-ból jön (múltbeli vetítési hibák); ha ahhoz nincs elég
    múlt, a linreg_forecast() reziduál-sávja marad."""
    clean = [v for v in series if v is not None]
    result = linreg_forecast(clean[-window:] if window is not None else clean, steps)
    if result is None:
        return None
    lower, upper = result["lower"], result["upper"]
    band = oos_band(clean, steps, window) if window is not None else None
    if band is not None:
        lower = [round(p - b, 3) for p, b in zip(result["forecast"], band)]
        upper = [round(p + b, 3) for p, b in zip(result["forecast"], band)]
    return {
        "horizon_label": horizon_label,
        "points": result["forecast"],
        "lower": lower,
        "upper": upper,
        "slope": result["slope"],
    }
