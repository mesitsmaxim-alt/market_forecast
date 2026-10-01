"""
Piaci előrejelző motor.

Beolvassa a külső tényezők (config/factors.json) és a szegmens-érzékenységek
(config/segments.json) definícióit, majd minden (hajtástípus x márkakategória x
évjárat-sáv) szegmensre kiszámol egy kitettségi pontszámot forgatókönyvenként
(pesszimista / alap / optimista).

A pontszám nem abszolút piaci előrejelzés, hanem RELATÍV IRÁNYJELZÉS: melyik
szegmenseket segítik vagy hátráltatják a vizsgált tényezők várható elmozdulásai
a következő időszakban.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"
DATA_DIR = Path(__file__).parent / "data"

# Azoknál a tényezőknél, ahol a nyers delta iránya fordított ahhoz képest,
# ahogy az érzékenységi együtthatót értelmezzük (pl. "akkumulátorár csökkenése
# jó az EV-knek", de a delta negatív csökkenésnél), itt fordítjuk meg.
FACTOR_DIRECTION = {
    "battery_cost": -1,
}

# A hajtástípus-momentum ELSŐDLEGES forrása az új autók hajtás szerinti
# megoszlása (Eurostat road_eqr_carpda, data/uj_hajtas.json): a momentum az
# új autókon belüli RÉSZESEDÉS változása, százalékpont/év. Ez valós keresleti
# elmozdulást mér. A korábbi állomány-CAGR (KSH sza0025) kis bázisú
# kategóriáknál bázishatást mért (pl. elektromos: +42%/év, miközben az
# állomány 2%-a) - ez már csak tartalék, ha az Eurostat-adat hiányzik.
MOMENTUM_CAP_PP = 10  # részesedés-változás normalizálási sapka (+-10 pp/év fölött nem skálázunk tovább)

# Tartalék (állomány-CAGR): hajtástípus -> KSH sza0025 hajtástípus-kulcs.
# A KSH nem különbözteti meg a PHEV-et a (nem tölthető) hibridtől, ezért a
# PHEV-hez is a "hibrid" kategória CAGR-ját használjuk proxyként.
DRIVETRAIN_TO_KSH = {
    "ICE": ["benzin", "dizel"],
    "HEV": ["hibrid"],
    "PHEV": ["hibrid"],
    "BEV": ["elektromos"],
}
MOMENTUM_WINDOW_YEARS = 3
# Mennyire nyomja el/erősítse a forgatókönyv-pontszámot a megfigyelt trend.
# Korábban 0.4 volt, de ez a gyakorlatban elnyomta a forgatókönyv-tényezőket
# (HEV/PHEV/BEV szegmenseknél a momentum önmagában meghaladta a teljes
# pontszámot, azaz a 6 tényező inkább csak levont belőle, nem hajtotta) -
# 0.15-re csökkentve a momentum kiegészítő jelzés marad, nem domináns tag.
MOMENTUM_WEIGHT = 0.15
MOMENTUM_CAP_PCT = 50  # CAGR normalizálási sapka (+-50%/év fölött már nem skálázunk tovább)

# A negyedéves forgalomba helyezési adat (KSH sza0070) zajosabb, mint az
# éves állomány-CAGR, ezért kisebb súllyal és nagyobb sapkával normalizáljuk.
REG_MOMENTUM_WEIGHT = 0.1
REG_MOMENTUM_CAP_PCT = 40


def load_momentum():
    """Valós hajtástípus-momentum: {hajtás: {"value", "kind"}}.

    Elsődlegesen az új autókon belüli részesedés átlagos éves változása
    (pp/év, MOMENTUM_WINDOW_YEARS évre, Eurostat) - kind="share_pp".
    Ha ez az adat nincs meg, tartalékként a KSH-állomány CAGR-ja (%/év) -
    kind="stock_cagr"."""
    path = DATA_DIR / "uj_hajtas.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        shares = data["shares_pct"]
        window = min(MOMENTUM_WINDOW_YEARS, len(data["years"]) - 1)
        if window >= 1:
            return {
                dt: {"value": (shares[dt][-1] - shares[dt][-1 - window]) / window, "kind": "share_pp"}
                for dt in ("ICE", "HEV", "PHEV", "BEV") if dt in shares
            }
    return {dt: {"value": v, "kind": "stock_cagr"} for dt, v in load_stock_momentum().items()}


def load_stock_momentum():
    """Tartalék: hajtástípus-momentum a KSH-állomány CAGR-jából (%/év)."""
    path = DATA_DIR / "jarmuallomany.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    years = data["years"]
    fuel_types = data["fuel_types"]
    window = min(MOMENTUM_WINDOW_YEARS, len(years) - 1)

    def cagr(series):
        start, end = series[-1 - window], series[-1]
        if start <= 0:
            return 0.0
        return ((end / start) ** (1 / window) - 1) * 100

    ksh_cagr = {key: cagr(series) for key, series in fuel_types.items()}

    momentum = {}
    for dt_key, ksh_keys in DRIVETRAIN_TO_KSH.items():
        values = [fuel_types[k][-1] for k in ksh_keys if k in fuel_types]
        weights = values if sum(values) > 0 else [1] * len(values)
        cagrs = [ksh_cagr[k] for k in ksh_keys if k in ksh_cagr]
        if not cagrs:
            continue
        weighted_cagr = sum(c * w for c, w in zip(cagrs, weights)) / sum(weights)
        momentum[dt_key] = weighted_cagr
    return momentum


def load_registration_momentum(brand_tiers: dict):
    """Márkakategória-momentum a KSH sza0070 negyedéves forgalomba helyezési
    adatból, a segments.json example_brands listái alapján. Azonos negyedév
    előző évhez képesti (YoY) növekedés, a márkánkénti legutóbbi volumennel
    súlyozva a kategórián belül."""
    path = DATA_DIR / "forgalomba.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    brands = data["brands"]
    if len(data["quarters"]) < 5:
        return {}

    def yoy(series):
        return (series[-1] / series[-5] - 1) * 100

    momentum = {}
    for bt_key, bt in brand_tiers.items():
        rows = [(brands[b][-1], yoy(brands[b])) for b in bt["example_brands"] if b in brands]
        if not rows:
            continue
        total_weight = sum(w for w, _ in rows)
        if total_weight <= 0:
            continue
        momentum[bt_key] = sum(w * y for w, y in rows) / total_weight
    return momentum


SCENARIOS = ("pesszimista", "alap", "optimista")

SCORE_LABELS = [
    (0.15, "Erős növekedés"),
    (0.05, "Növekedés"),
    (-0.05, "Stagnálás"),
    (-0.15, "Visszaesés"),
    (float("-inf"), "Erős visszaesés"),
]


def classify(score: float) -> str:
    for threshold, label in SCORE_LABELS:
        if score >= threshold:
            return label
    return SCORE_LABELS[-1][1]


def load_config():
    with open(CONFIG_DIR / "factors.json", encoding="utf-8") as f:
        factors = json.load(f)["factors"]
    with open(CONFIG_DIR / "segments.json", encoding="utf-8") as f:
        segments = json.load(f)
    return factors, segments


@dataclass
class SegmentResult:
    drivetrain: str
    drivetrain_label: str
    brand_tier: str
    brand_tier_label: str
    example_brands: list
    year_bucket: str
    year_bucket_label: str
    scores: dict  # scenario -> float
    drivers: dict  # scenario -> [(factor_label, contribution), ...] sorted desc by abs


def compute_segments():
    factors, segments = load_config()
    drivetrains = segments["drivetrains"]
    brand_tiers = segments["brand_tiers"]
    year_buckets = segments["year_buckets"]
    momentum = load_momentum()
    reg_momentum = load_registration_momentum(brand_tiers)

    results = []
    for dt_key, dt in drivetrains.items():
        for bt_key, bt in brand_tiers.items():
            for yb_key, yb in year_buckets.items():
                scores = {}
                drivers = {}
                for scenario in SCENARIOS:
                    total = 0.0
                    contribs = []
                    for factor_key, factor in factors.items():
                        delta = factor["scenarios"][scenario]
                        direction = FACTOR_DIRECTION.get(factor_key, 1)
                        effective_delta = delta * direction / 100.0  # normalizált arány

                        sens = dt["sensitivity"].get(factor_key, 0.0)
                        sens += bt["sensitivity"].get(factor_key, 0.0)
                        sens += yb.get("extra_sensitivity", {}).get(factor_key, 0.0)

                        contribution = sens * effective_delta
                        total += contribution
                        contribs.append((factor["label"], contribution))

                    if dt_key in momentum:
                        m = momentum[dt_key]
                        if m["kind"] == "share_pp":
                            normalized = max(-1.0, min(1.0, m["value"] / MOMENTUM_CAP_PP))
                            label = f"Megfigyelt piaci momentum (új autók részesedése, {m['value']:+.1f} pp/év)"
                        else:
                            normalized = max(-1.0, min(1.0, m["value"] / MOMENTUM_CAP_PCT))
                            label = f"Megfigyelt piaci momentum (KSH állomány, {m['value']:+.1f}%/év)"
                        momentum_term = normalized * MOMENTUM_WEIGHT
                        total += momentum_term
                        contribs.append((label, momentum_term))

                    if bt_key in reg_momentum:
                        yoy_pct = reg_momentum[bt_key]
                        normalized = max(-1.0, min(1.0, yoy_pct / REG_MOMENTUM_CAP_PCT))
                        reg_term = normalized * REG_MOMENTUM_WEIGHT
                        total += reg_term
                        contribs.append(
                            (f"Megfigyelt piaci momentum (forgalomba helyezés, {yoy_pct:+.1f}% YoY)", reg_term)
                        )

                    weighted = total * yb["weight"]
                    scores[scenario] = weighted
                    contribs.sort(key=lambda c: abs(c[1]), reverse=True)
                    drivers[scenario] = contribs

                results.append(
                    SegmentResult(
                        drivetrain=dt_key,
                        drivetrain_label=dt["label"],
                        brand_tier=bt_key,
                        brand_tier_label=bt["label"],
                        example_brands=bt["example_brands"],
                        year_bucket=yb_key,
                        year_bucket_label=yb["label"],
                        scores=scores,
                        drivers=drivers,
                    )
                )
    return results, factors
