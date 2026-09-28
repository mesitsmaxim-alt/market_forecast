#!/usr/bin/env python3
"""
A config/factors.json becsléseinek kalibrálása a már bekötött valós adatokkal.

Jelenleg: az oil_price tényező "alap" forgatókönyvét a holtankoljak.hu-ról
letöltött ÉLŐ, mindig aktuális üzemanyagár-adatból (data/uzemanyagar_elo.json)
számolt tényleges YoY árváltozásra állítja, a pesszimista/optimista sávot
pedig ez köré építi.

Előfeltétel: futtasd előbb a fetchers/fetch_uzemanyag_elo.py-t.

Használat:
    python3 calibrate_factors.py
Ez felülírja a config/factors.json mind a 8 tényezőjének forgatókönyv-értékeit.
A battery_cost, ev_tariffs és co2_regulation tényezők KÉZI, forrásmegjelölt
adatfájlokból (data/akkuar.json, data/ev_vamok.json, data/co2_szabalyozas.json)
kalibrálódnak, mert ezekhez nincs gépileg lekérdezhető forrás — ha egy ilyen
fájl "updated" dátuma túl régi, a note-ba és a konzolra figyelmeztetés kerül.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config" / "factors.json"
FUEL_LIVE_DATA_PATH = Path(__file__).parent / "data" / "uzemanyagar_elo.json"
MAKRO_DATA_PATH = Path(__file__).parent / "data" / "makro.json"
CHARGING_DATA_PATH = Path(__file__).parent / "data" / "toltoinfra.json"
SZENTIMENT_DATA_PATH = Path(__file__).parent / "data" / "szentiment.json"
REALJOVEDELEM_DATA_PATH = Path(__file__).parent / "data" / "realjovedelem.json"
AKKUAR_DATA_PATH = Path(__file__).parent / "data" / "akkuar.json"
EV_VAMOK_DATA_PATH = Path(__file__).parent / "data" / "ev_vamok.json"
CO2_DATA_PATH = Path(__file__).parent / "data" / "co2_szabalyozas.json"

SPREAD_PCT = 8  # a pesszimista/optimista sáv fél-szélessége az alap körül
FINANCING_SPREAD_PP = 1.5  # a finanszírozási költség sávjának fél-szélessége (percentpont)
CHARGING_SPREAD_PCT = 10  # a töltőinfra sávjának fél-szélessége
SENTIMENT_SPREAD_PONT = 10  # a fogyasztói szentiment sávjának fél-szélessége (balance-pont)
PURCHASING_POWER_SPREAD_PCT = 6  # a reáljövedelem sávjának fél-szélessége
BATTERY_SPREAD_PCT = 6  # az akkumulátorár sávjának fél-szélessége
TARIFF_SPREAD_PP = 10  # az EV-vámok sávjának fél-szélessége (effektív átlagvám, pp)
CO2_SPREAD = 4  # a CO2-szabályozási nyomás sávjának fél-szélessége (%/év)

# Kézi adatfájlok elavulási küszöbe (nap): az akkuár évente frissül (BNEF,
# december), a vám- és CO2-idővonal eseményszerűen, ezért azt gyakrabban
# kell átnézni.
STALE_DAYS = {"akkuar": 395, "ev_vamok": 183, "co2_szabalyozas": 183}
HORIZON_DAYS = 365


def compute_oil_price_trend() -> tuple[float, str]:
    """Mindig a JELENLEGI üzemanyagárból (holtankoljak.hu, napi frissülő)
    számolja a tényleges éves (YoY) árváltozást - a tábla beépítve tartalmaz
    egy ~1 évvel korábbi összehasonlító oszlopot is, így egyetlen friss
    lekérésből adódik a trend, nem kell hosszú saját idősort gyűjteni."""
    data = json.loads(FUEL_LIVE_DATA_PATH.read_text(encoding="utf-8"))
    fuels = data["fuels"]
    current_period, _month_ago_period, year_ago_period = data["periods"]

    benzin_now = fuels["95-ös Benzin E10"][current_period]
    benzin_1y = fuels["95-ös Benzin E10"][year_ago_period]
    dizel_now = fuels["Gázolaj"][current_period]
    dizel_1y = fuels["Gázolaj"][year_ago_period]

    avg_now = (benzin_now + dizel_now) / 2
    avg_1y = (benzin_1y + dizel_1y) / 2
    annualized_pct = (avg_now / avg_1y - 1) * 100

    note = (
        f"Kalibrálva: holtankoljak.hu ÉLŐ, napi frissülő adatából, a HU "
        f"95-ös benzin+gázolaj átlagár tényleges éves (YoY) változása "
        f"({current_period} vs. {year_ago_period}: {annualized_pct:+.1f}%). "
        f"Forrás: data/uzemanyagar_elo.json (fetchers/fetch_uzemanyag_elo.py, "
        f"majd calibrate_factors.py futtatásának eredménye) - ez MINDIG a "
        f"legfrissebb elérhető árat használja, nem egy befagyott pillanatfelvételt."
    )
    return annualized_pct, note


def compute_financing_cost_trend() -> tuple[float, str]:
    data = json.loads(MAKRO_DATA_PATH.read_text(encoding="utf-8"))
    rate = data["alapkamat"]
    dates, values = rate["dates"], rate["values"]

    import datetime

    last_date = datetime.date.fromisoformat(dates[-1])
    target = last_date - datetime.timedelta(days=365)
    candidates = [(d, v) for d, v in zip(dates, values) if datetime.date.fromisoformat(d) <= target]
    rate_1y_ago = candidates[-1][1] if candidates else values[0]
    change_pp = values[-1] - rate_1y_ago

    # A tényező a KÖVETKEZŐ 12 hónap várható elmozdulását jelenti - a
    # megfigyelt 12 havi trendet vetítjük előre "alap" feltételezésként
    # (azaz feltételezzük a jelenlegi irány folytatódását), amíg nincs
    # explicit MNB-előrejelzés bekötve.
    note = (
        f"Kalibrálva: MNB alapkamat-idősor alapján, a bázisráta "
        f"{dates[-1]}-ig tartó 12 hónapos változása ({change_pp:+.2f} "
        f"százalékpont) mint a folytatódó trend feltételezése. "
        f"Forrás: data/makro.json (calibrate_factors.py futtatásának eredménye)."
    )
    return change_pp, note


def compute_charging_infra_trend() -> tuple[float, str]:
    data = json.loads(CHARGING_DATA_PATH.read_text(encoding="utf-8"))
    qc = data["quarterly_counts"]
    ac, dc, quarters = qc["ac"], qc["dc"], qc["quarters"]
    total = [a + d for a, d in zip(ac, dc)]
    if len(total) < 5:
        raise ValueError("Nincs elég negyedéves adat a töltőinfra YoY számításához")
    yoy_pct = (total[-1] / total[-5] - 1) * 100

    note = (
        f"Kalibrálva: EAFO adat alapján (kézzel importálva, {quarters[-1]}-ig), "
        f"a magyarországi nyilvános AC+DC töltőpontszám éves (YoY) növekedése "
        f"({yoy_pct:+.1f}%). Forrás: data/toltoinfra.json "
        f"(import_eafo_charging.py, majd calibrate_factors.py futtatásának eredménye). "
        f"Megjegyzés: ez az adat NEM automatikusan frissül — az EAFO dashboard "
        f"JS-alapú, kézi CSV-export szükséges hozzá (ld. import_eafo_charging.py)."
    )
    return yoy_pct, note


def compute_consumer_sentiment_trend() -> tuple[float, str]:
    data = json.loads(SZENTIMENT_DATA_PATH.read_text(encoding="utf-8"))
    mp = data["major_purchases_intention"]
    months = data["months"]
    if len(mp) < 13:
        raise ValueError("Nincs elég havi adat a szentiment 12 havi változásához")
    change_1y = mp[-1] - mp[-13]

    note = (
        f"Kalibrálva: Eurostat ei_bsco_m (\"tartós fogyasztási cikk vásárlási "
        f"szándék\", HU, szezonálisan igazítva) alapján, a {months[-13]}–"
        f"{months[-1]} közötti 12 havi változás ({change_1y:+.1f} balance-pont) "
        f"mint a folytatódó trend feltételezése. Forrás: data/szentiment.json "
        f"(calibrate_factors.py futtatásának eredménye)."
    )
    return change_1y, note


def compute_purchasing_power_trend() -> tuple[float, str]:
    data = json.loads(REALJOVEDELEM_DATA_PATH.read_text(encoding="utf-8"))
    years = data["years"]
    income = data["real_income_yoy_pct"]
    wage = data["real_wage_yoy_pct"]

    # a reáljövedelem (teljes, egy főre jutó) a jobb proxy, de egy évvel
    # később publikálódik, mint a reálkereset - ha az utolsó évre hiányzik,
    # a reálkeresetre esünk vissza
    last_i = len(years) - 1
    if income[last_i] is not None:
        value, year, used = income[last_i], years[last_i], "reáljövedelem"
    else:
        value, year, used = wage[last_i], years[last_i], "reálkereset (a reáljövedelem még nem publikált erre az évre)"

    note = (
        f"Kalibrálva: KSH gdp0035 (reáljövedelem/reálkereset-index) alapján, "
        f"a {year}. évi YoY {used} ({value:+.1f}%) mint a folytatódó trend "
        f"feltételezése. Forrás: data/realjovedelem.json "
        f"(calibrate_factors.py futtatásának eredménye)."
    )
    return value, note


def staleness_warning(data: dict, key: str) -> str | None:
    """Figyelmeztető szöveg, ha a kézi adatfájl 'updated' dátuma régebbi a
    küszöbnél — különben None."""
    import datetime

    updated = datetime.date.fromisoformat(data["updated"])
    age_days = (datetime.date.today() - updated).days
    if age_days <= STALE_DAYS[key]:
        return None
    return (f"FIGYELEM: a data/{key}.json utoljára {data['updated']}-én frissült "
            f"({age_days} napja) — ellenőrizd, van-e újabb forrásadat.")


def compute_battery_cost_trend() -> tuple[float, str, str | None]:
    data = json.loads(AKKUAR_DATA_PATH.read_text(encoding="utf-8"))
    yoy_pct = data["yoy_pct_reported"]
    warning = staleness_warning(data, "akkuar")

    # A BNEF minden évben reálértéken újraszámolja a korábbi éveket, ezért a
    # közleményben megadott YoY-t használjuk, nem két felmérés nominális számát.
    note = (
        f"Kalibrálva: BloombergNEF {data['survey_year']}. évi akkumulátorár-felmérése "
        f"alapján (csomagár {data['latest_pack_price_usd_kwh']} $/kWh, BEV-csomag "
        f"{data['latest_bev_pack_price_usd_kwh']} $/kWh), a közölt éves változás "
        f"({yoy_pct:+.1f}%) mint a folytatódó trend feltételezése. Negatív delta = "
        f"olcsóbb akkumulátor (a modell az előjelet megfordítja). Forrás: "
        f"data/akkuar.json (kézi adatbevitel, calibrate_factors.py futtatásának eredménye)."
    )
    if warning:
        note += " " + warning
    return yoy_pct, note, warning


def compute_ev_tariffs_trend() -> tuple[float, str, str | None]:
    import datetime

    data = json.loads(EV_VAMOK_DATA_PATH.read_text(encoding="utf-8"))
    warning = staleness_warning(data, "ev_vamok")
    today = datetime.date.today()
    horizon = datetime.timedelta(days=HORIZON_DAYS)

    # Alap: az elmúlt 12 hónap hatályba lépett eseményei (folytatódó trend, a
    # többi tényezővel egyező logika) + a következő 12 hónapra már elfogadott
    # (hatályos státuszú, de jövőbeli dátumú) események. Javaslat státuszú
    # eseményeket nem számolunk bele.
    counted = [
        e for e in data["events"]
        if e["status"] == "hatályos"
        and today - horizon <= datetime.date.fromisoformat(e["date"]) <= today + horizon
    ]
    change_pp = sum(e["impact_pp"] for e in counted)
    event_list = "; ".join(f"{e['date']}: {e['impact_pp']:+.1f} pp" for e in counted) or "nincs"

    note = (
        f"Kalibrálva: EU kiegyenlítő vámok kínai BEV-ekre (DG TRADE) alapján — az "
        f"effektív átlagvám becsült változása a ±12 hónapos ablakba eső hatályos "
        f"eseményekből ({event_list}; összesen {change_pp:+.1f} pp). Pozitív delta = "
        f"vámemelés. Forrás: data/ev_vamok.json (kézi adatbevitel, az eseményenkénti "
        f"hatás durva becslés — ld. impact_basis)."
    )
    if warning:
        note += " " + warning
    return change_pp, note, warning


def compute_co2_regulation_trend() -> tuple[float, str, str | None]:
    import datetime

    data = json.loads(CO2_DATA_PATH.read_text(encoding="utf-8"))
    warning = staleness_warning(data, "co2_szabalyozas")
    today = datetime.date.today()

    milestones = sorted(
        (m for m in data["milestones"] if m["status"] == "hatályos"),
        key=lambda m: m["from"],
    )
    current = [m for m in milestones if datetime.date.fromisoformat(m["from"]) <= today][-1]
    upcoming = [m for m in milestones if datetime.date.fromisoformat(m["from"]) > today]
    if not upcoming:
        raise ValueError("Nincs jövőbeli CO2-mérföldkő a data/co2_szabalyozas.json-ban")
    nxt = upcoming[0]

    # Szabályozási nyomás = a következő mérföldkőig évente (lineárisan)
    # szükséges flottaszintű csökkentés, %/év.
    years_left = (datetime.date.fromisoformat(nxt["from"]) - today).days / 365.25
    reduction_pct = (1 - nxt["target_g_km"] / current["target_g_km"]) * 100
    pressure = reduction_pct / years_left

    note = (
        f"Kalibrálva: EU flotta-CO2 célok (2019/631 rendelet) alapján — a jelenlegi "
        f"{current['target_g_km']} g/km célról a {nxt['from'][:4]}-es "
        f"{nxt['target_g_km']} g/km-re {years_left:.1f} év alatt szükséges "
        f"{reduction_pct:.1f}%-os csökkentés, évesítve ({pressure:.1f}%/év) mint "
        f"szabályozási nyomás. Függőben lévő javaslatok (nem számolva): "
        f"{len(data.get('proposals', []))} db. Forrás: data/co2_szabalyozas.json (kézi adatbevitel)."
    )
    if warning:
        note += " " + warning
    return pressure, note, warning


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    annualized_pct, oil_note = compute_oil_price_trend()
    oil = config["factors"]["oil_price"]
    oil["note"] = oil_note
    oil["scenarios"] = {
        "pesszimista": round(annualized_pct - SPREAD_PCT, 1),
        "alap": round(annualized_pct, 1),
        "optimista": round(annualized_pct + SPREAD_PCT, 1),
    }

    financing_pp, financing_note = compute_financing_cost_trend()
    financing = config["factors"]["financing_cost"]
    financing["note"] = financing_note
    financing["scenarios"] = {
        "pesszimista": round(financing_pp + FINANCING_SPREAD_PP, 1),
        "alap": round(financing_pp, 1),
        "optimista": round(financing_pp - FINANCING_SPREAD_PP, 1),
    }

    charging_pct, charging_note = compute_charging_infra_trend()
    charging = config["factors"]["charging_infra"]
    charging["note"] = charging_note
    charging["scenarios"] = {
        "pesszimista": round(charging_pct - CHARGING_SPREAD_PCT, 1),
        "alap": round(charging_pct, 1),
        "optimista": round(charging_pct + CHARGING_SPREAD_PCT, 1),
    }

    sentiment_pont, sentiment_note = compute_consumer_sentiment_trend()
    sentiment = config["factors"]["consumer_sentiment"]
    sentiment["note"] = sentiment_note
    sentiment["scenarios"] = {
        "pesszimista": round(sentiment_pont - SENTIMENT_SPREAD_PONT, 1),
        "alap": round(sentiment_pont, 1),
        "optimista": round(sentiment_pont + SENTIMENT_SPREAD_PONT, 1),
    }

    pp_pct, pp_note = compute_purchasing_power_trend()
    pp = config["factors"]["purchasing_power"]
    pp["note"] = pp_note
    pp["scenarios"] = {
        "pesszimista": round(pp_pct - PURCHASING_POWER_SPREAD_PCT, 1),
        "alap": round(pp_pct, 1),
        "optimista": round(pp_pct + PURCHASING_POWER_SPREAD_PCT, 1),
    }

    warnings = []

    battery_pct, battery_note, w = compute_battery_cost_trend()
    warnings.append(w)
    battery = config["factors"]["battery_cost"]
    battery["note"] = battery_note
    battery["scenarios"] = {
        "pesszimista": round(battery_pct + BATTERY_SPREAD_PCT, 1),
        "alap": round(battery_pct, 1),
        "optimista": round(battery_pct - BATTERY_SPREAD_PCT, 1),
    }

    tariff_pp, tariff_note, w = compute_ev_tariffs_trend()
    warnings.append(w)
    tariffs = config["factors"]["ev_tariffs"]
    tariffs["unit"] = "pp"  # effektív átlagvám változása, százalékpontban
    tariffs["note"] = tariff_note
    tariffs["scenarios"] = {
        "pesszimista": round(tariff_pp + TARIFF_SPREAD_PP, 1),
        "alap": round(tariff_pp, 1),
        "optimista": round(tariff_pp - TARIFF_SPREAD_PP, 1),
    }

    co2_pressure, co2_note, w = compute_co2_regulation_trend()
    warnings.append(w)
    co2 = config["factors"]["co2_regulation"]
    co2["unit"] = "%/év"  # évesített szükséges flotta-CO2 csökkentés
    co2["note"] = co2_note
    co2["scenarios"] = {
        "pesszimista": round(co2_pressure - CO2_SPREAD, 1),
        "alap": round(co2_pressure, 1),
        "optimista": round(co2_pressure + CO2_SPREAD, 1),
    }

    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"config/factors.json frissítve. oil_price.alap = {annualized_pct:+.1f}%/év, "
          f"financing_cost.alap = {financing_pp:+.1f}pp, "
          f"charging_infra.alap = {charging_pct:+.1f}%/év, "
          f"consumer_sentiment.alap = {sentiment_pont:+.1f}pont, "
          f"purchasing_power.alap = {pp_pct:+.1f}%, "
          f"battery_cost.alap = {battery_pct:+.1f}%, "
          f"ev_tariffs.alap = {tariff_pp:+.1f}pp, "
          f"co2_regulation.alap = {co2_pressure:.1f}%/év")
    for w in warnings:
        if w:
            print(w)


if __name__ == "__main__":
    main()
