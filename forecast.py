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


def forecast_card(series: list[float], steps: int, horizon_label: str,
                  window: int | None = None) -> dict | None:
    """linreg_forecast() eredményét a dashboard-kártyákhoz illő alakra hozza.

    `window`: csak az utolsó ennyi (nem None) adatpontra illesztünk egyenest.
    A teljes, évtizedes idősorra illesztett egyenes félrevezető (pl. az
    alapkamatnál a 90-es évek 20% feletti szintje negatív kamatot "jósolt",
    a gyorsuló hibrid/elektromos részesedésnél a jelenleginél kisebbet) - a
    cél a JELENLEGI trend iránya, ezért a friss ablak a helyes alap. A
    megjelenített történeti görbe ettől még a teljes idősor marad."""
    clean = [v for v in series if v is not None]
    if window is not None:
        clean = clean[-window:]
    result = linreg_forecast(clean, steps)
    if result is None:
        return None
    return {
        "horizon_label": horizon_label,
        "points": result["forecast"],
        "lower": result["lower"],
        "upper": result["upper"],
        "slope": result["slope"],
    }
