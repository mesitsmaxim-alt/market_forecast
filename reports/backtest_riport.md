# Backtesting — 2026-10-01

A `config/segments.json`-ban kézzel megadott érzékenységi együtthatók visszamérése valós, történeti adaton. **Csak 3 a 8 tényezőből tesztelhető** (finanszírozási költség, vásárlóerő, fogyasztói szándék) — ehhez van elég hosszú, éves bontású valós idősorunk. A többi tényezőhöz (olajár, akkumulátorár, töltőinfra, EV-vám, CO2-szabályozás) nincs elég hosszú visszamenő adat a projektben, ezért ez a backtest **a modell egy részét, nem az egészét** validálja.

> **Módszertani megjegyzés:** a "megfigyelt piaci momentum" tag (`engine.py`) szándékosan KI van hagyva ebből a tesztből, mert azt is ugyanabból a KSH-idősorból számoljuk, amit itt tényleges kimenetként használunk — bevonása körkörös lenne. A backtest tehát kifejezetten azt méri, van-e előrejelző ereje a forgatókönyv-tényezőknek ÖNMAGUKBAN, a nyers trendtől függetlenül.

## BEV vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.04
- **Hit rate** (előjel-egyezés): 65% (n=23 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.042 | -0.02317 | ❌ |
| 2004 | -0.106 | +0.00727 | ❌ |
| 2005 | -0.140 | +0.03750 | ❌ |
| 2006 | -0.101 | -0.03847 | ✅ |
| 2007 | -0.053 | -0.07017 | ✅ |
| 2008 | -0.026 | -0.01943 | ✅ |
| 2009 | +0.012 | -0.03270 | ❌ |
| 2010 | +0.099 | +0.07257 | ✅ |
| 2011 | +0.208 | -0.02120 | ❌ |
| 2012 | +0.309 | -0.02700 | ❌ |
| 2013 | +0.149 | +0.07153 | ✅ |
| 2014 | +0.099 | +0.08640 | ✅ |
| 2015 | +0.088 | +0.02223 | ✅ |
| 2016 | +0.139 | +0.02457 | ✅ |
| 2017 | +0.263 | +0.03430 | ✅ |
| 2018 | +0.357 | +0.03440 | ✅ |
| 2019 | +0.477 | +0.01557 | ✅ |
| 2020 | +0.915 | -0.05210 | ❌ |
| 2021 | +1.332 | +0.03220 | ✅ |
| 2022 | +1.417 | -0.08233 | ❌ |
| 2023 | +1.440 | +0.01200 | ✅ |
| 2024 | +1.968 | +0.07693 | ✅ |
| 2025 | +2.290 | +0.00583 | ✅ |

## Hibrid vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.04
- **Hit rate** (előjel-egyezés): 65% (n=23 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.064 | -0.00414 | ❌ |
| 2004 | -0.099 | +0.00299 | ❌ |
| 2005 | -0.141 | +0.01053 | ❌ |
| 2006 | -0.097 | -0.00929 | ✅ |
| 2007 | -0.045 | -0.01859 | ✅ |
| 2008 | -0.004 | -0.00536 | ✅ |
| 2009 | +0.026 | -0.00920 | ❌ |
| 2010 | +0.112 | +0.01807 | ✅ |
| 2011 | +0.228 | -0.00428 | ❌ |
| 2012 | +0.329 | -0.00727 | ❌ |
| 2013 | +0.171 | +0.01843 | ✅ |
| 2014 | +0.133 | +0.02265 | ✅ |
| 2015 | +0.137 | +0.00651 | ✅ |
| 2016 | +0.242 | +0.00724 | ✅ |
| 2017 | +0.429 | +0.01015 | ✅ |
| 2018 | +0.588 | +0.01065 | ✅ |
| 2019 | +0.774 | +0.00559 | ✅ |
| 2020 | +1.524 | -0.01325 | ❌ |
| 2021 | +2.122 | +0.01015 | ✅ |
| 2022 | +2.065 | -0.01973 | ❌ |
| 2023 | +2.114 | +0.00338 | ✅ |
| 2024 | +2.685 | +0.02101 | ✅ |
| 2025 | +2.923 | +0.00188 | ✅ |

## Értelmezés

A hit rate a véletlennél (50%) jobb, de a korreláció gyenge — ez azt jelzi, hogy az érzékenységi együtthatók **iránya** részben helyes megérzés volt, de a **nagyságrendjük** (relatív súlyuk egymáshoz képest) nincs jól kalibrálva a valósághoz. Ennek egy valószínű oka: a BEV-térnyerés tényleges mozgatórugói (akkumulátorár, töltőinfra, EU-szabályozás) pont azok, amikhez nincs hosszú történeti adatunk — ez a backtest szükségszerűen vak foltokkal dolgozik. A korrelációt és hit rate-et érdemes újraszámolni, ha sikerül a hiányzó tényezőkhöz is valós történeti idősort szerezni.