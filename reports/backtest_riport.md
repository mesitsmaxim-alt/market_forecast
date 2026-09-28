# Backtesting — 2026-09-28

A `config/segments.json`-ban kézzel megadott érzékenységi együtthatók visszamérése valós, történeti adaton. **Csak 3 a 8 tényezőből tesztelhető** (finanszírozási költség, vásárlóerő, fogyasztói szándék) — ehhez van elég hosszú, éves bontású valós idősorunk. A többi tényezőhöz (olajár, akkumulátorár, töltőinfra, EV-vám, CO2-szabályozás) nincs elég hosszú visszamenő adat a projektben, ezért ez a backtest **a modell egy részét, nem az egészét** validálja.

> **Módszertani megjegyzés:** a "megfigyelt piaci momentum" tag (`engine.py`) szándékosan KI van hagyva ebből a tesztből, mert azt is ugyanabból a KSH-idősorból számoljuk, amit itt tényleges kimenetként használunk — bevonása körkörös lenne. A backtest tehát kifejezetten azt méri, van-e előrejelző ereje a forgatókönyv-tényezőknek ÖNMAGUKBAN, a nyers trendtől függetlenül.

## BEV vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.05
- **Hit rate** (előjel-egyezés): 64% (n=22 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.042 | -0.02313 | ❌ |
| 2004 | -0.106 | +0.00743 | ❌ |
| 2005 | -0.140 | +0.03733 | ❌ |
| 2006 | -0.101 | -0.03843 | ✅ |
| 2007 | -0.053 | -0.07020 | ✅ |
| 2008 | -0.026 | -0.01940 | ✅ |
| 2009 | +0.012 | -0.03273 | ❌ |
| 2010 | +0.099 | +0.07267 | ✅ |
| 2011 | +0.208 | -0.02130 | ❌ |
| 2012 | +0.309 | -0.02690 | ❌ |
| 2013 | +0.149 | +0.07140 | ✅ |
| 2014 | +0.099 | +0.08650 | ✅ |
| 2015 | +0.088 | +0.02217 | ✅ |
| 2016 | +0.139 | +0.02467 | ✅ |
| 2017 | +0.263 | +0.03427 | ✅ |
| 2018 | +0.357 | +0.03443 | ✅ |
| 2019 | +0.477 | +0.01580 | ✅ |
| 2020 | +0.915 | -0.05187 | ❌ |
| 2021 | +1.332 | +0.03233 | ✅ |
| 2022 | +1.417 | -0.08180 | ❌ |
| 2023 | +1.440 | +0.01163 | ✅ |
| 2024 | +1.968 | +0.07670 | ✅ |

## Hibrid vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.05
- **Hit rate** (előjel-egyezés): 64% (n=22 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.064 | -0.00413 | ❌ |
| 2004 | -0.099 | +0.00303 | ❌ |
| 2005 | -0.141 | +0.01048 | ❌ |
| 2006 | -0.097 | -0.00928 | ✅ |
| 2007 | -0.045 | -0.01860 | ✅ |
| 2008 | -0.004 | -0.00535 | ✅ |
| 2009 | +0.026 | -0.00921 | ❌ |
| 2010 | +0.112 | +0.01809 | ✅ |
| 2011 | +0.228 | -0.00430 | ❌ |
| 2012 | +0.329 | -0.00725 | ❌ |
| 2013 | +0.171 | +0.01840 | ✅ |
| 2014 | +0.133 | +0.02267 | ✅ |
| 2015 | +0.137 | +0.00649 | ✅ |
| 2016 | +0.242 | +0.00727 | ✅ |
| 2017 | +0.429 | +0.01014 | ✅ |
| 2018 | +0.588 | +0.01066 | ✅ |
| 2019 | +0.774 | +0.00568 | ✅ |
| 2020 | +1.524 | -0.01317 | ❌ |
| 2021 | +2.122 | +0.01018 | ✅ |
| 2022 | +2.065 | -0.01955 | ❌ |
| 2023 | +2.114 | +0.00326 | ✅ |
| 2024 | +2.685 | +0.02093 | ✅ |

## Értelmezés

A hit rate a véletlennél (50%) jobb, de a korreláció gyenge — ez azt jelzi, hogy az érzékenységi együtthatók **iránya** részben helyes megérzés volt, de a **nagyságrendjük** (relatív súlyuk egymáshoz képest) nincs jól kalibrálva a valósághoz. Ennek egy valószínű oka: a BEV-térnyerés tényleges mozgatórugói (akkumulátorár, töltőinfra, EU-szabályozás) pont azok, amikhez nincs hosszú történeti adatunk — ez a backtest szükségszerűen vak foltokkal dolgozik. A korrelációt és hit rate-et érdemes újraszámolni, ha sikerül a hiányzó tényezőkhöz is valós történeti idősort szerezni.