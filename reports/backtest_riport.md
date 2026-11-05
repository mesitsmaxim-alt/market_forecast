# Backtesting — 2026-11-05

A `config/segments.json`-ban kézzel megadott érzékenységi együtthatók visszamérése valós, történeti adaton. **Csak 4 a 8 tényezőből tesztelhető** (finanszírozási költség, vásárlóerő, fogyasztói szándék, üzemanyagár — az utóbbi az Eurostat HICP-üzemanyagindexéből) — ehhez van elég hosszú, éves bontású valós idősorunk. A többi tényezőhöz (akkumulátorár, töltőinfra, EV-vám, CO2-szabályozás) nincs elég hosszú visszamenő adat a projektben, ezért ez a backtest **a modell egy részét, nem az egészét** validálja.

> **Módszertani megjegyzés:** a "megfigyelt piaci momentum" tag (`engine.py`) szándékosan KI van hagyva ebből a tesztből. A hajtás-momentum ma már az új autók hajtás szerinti részesedéséből jön (Eurostat, csak 2020-tól), nem az itt kimenetként használt KSH-állományból, de ugyanazt a piaci átrendeződést méri, így bevonása részben körkörös lenne, és a 2020 előtti évekre nincs is adata. A backtest tehát kifejezetten azt méri, van-e előrejelző ereje a forgatókönyv-tényezőknek ÖNMAGUKBAN, a nyers trendtől függetlenül.

## BEV vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.15
- **Hit rate** (előjel-egyezés): 61% (n=23 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.042 | +0.05405 | ✅ |
| 2004 | -0.106 | +0.10111 | ❌ |
| 2005 | -0.140 | +0.19900 | ❌ |
| 2006 | -0.101 | +0.08291 | ❌ |
| 2007 | -0.053 | -0.08666 | ✅ |
| 2008 | -0.026 | +0.15876 | ❌ |
| 2009 | +0.012 | -0.15122 | ❌ |
| 2010 | +0.099 | +0.42838 | ✅ |
| 2011 | +0.208 | +0.23754 | ✅ |
| 2012 | +0.309 | +0.18948 | ✅ |
| 2013 | +0.149 | +0.03805 | ✅ |
| 2014 | +0.099 | +0.04947 | ✅ |
| 2015 | +0.088 | -0.18561 | ❌ |
| 2016 | +0.139 | -0.09399 | ❌ |
| 2017 | +0.263 | +0.15786 | ✅ |
| 2018 | +0.357 | +0.16833 | ✅ |
| 2019 | +0.477 | +0.02206 | ✅ |
| 2020 | +0.915 | -0.14682 | ❌ |
| 2021 | +1.332 | +0.42289 | ✅ |
| 2022 | +1.417 | +0.14904 | ✅ |
| 2023 | +1.440 | +0.37444 | ✅ |
| 2024 | +1.968 | +0.08302 | ✅ |
| 2025 | +2.290 | -0.02878 | ❌ |

## Hibrid vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.17
- **Hit rate** (előjel-egyezés): 52% (n=23 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.064 | +0.05943 | ✅ |
| 2004 | -0.099 | +0.08027 | ❌ |
| 2005 | -0.141 | +0.14353 | ❌ |
| 2006 | -0.097 | +0.09067 | ❌ |
| 2007 | -0.045 | -0.03217 | ✅ |
| 2008 | -0.004 | +0.14137 | ❌ |
| 2009 | +0.026 | -0.10679 | ❌ |
| 2010 | +0.112 | +0.31109 | ✅ |
| 2011 | +0.228 | +0.20880 | ✅ |
| 2012 | +0.329 | +0.17096 | ✅ |
| 2013 | +0.171 | -0.00905 | ❌ |
| 2014 | +0.133 | -0.00784 | ❌ |
| 2015 | +0.137 | -0.16460 | ❌ |
| 2016 | +0.242 | -0.09045 | ❌ |
| 2017 | +0.429 | +0.11192 | ✅ |
| 2018 | +0.588 | +0.12096 | ✅ |
| 2019 | +0.774 | +0.01092 | ✅ |
| 2020 | +1.524 | -0.09124 | ❌ |
| 2021 | +2.122 | +0.33188 | ✅ |
| 2022 | +2.065 | +0.17081 | ✅ |
| 2023 | +2.114 | +0.30186 | ✅ |
| 2024 | +2.685 | +0.02604 | ✅ |
| 2025 | +2.923 | -0.02666 | ❌ |

## Értelmezés

- **BEV vs. ICE:** a találati arány (61%) statisztikailag nem különböztethető meg a véletlentől (50%; p = 0.40, n = 23); a korreláció (+0.15) nem különböztethető meg a nullától (p = 0.51), a pontszámok nagyságrendje nem bizonyíthatóan követi a tényleges elmozdulást. Mivel a tényleges változás 78%-ban pozitív, a véletlen egyezés várható aránya valójában 64%.
- **Hibrid vs. ICE:** a találati arány (52%) statisztikailag nem különböztethető meg a véletlentől (50%; p = 1.00, n = 23); a korreláció (+0.17) nem különböztethető meg a nullától (p = 0.45), a pontszámok nagyságrendje nem bizonyíthatóan követi a tényleges elmozdulást. Mivel a tényleges változás 78%-ban pozitív, a véletlen egyezés várható aránya valójában 59%.

Az érzékenységi együtthatók szakértői becslések. Ha az eredmény nem szignifikáns, két magyarázat lehetséges, és a backtest nem dönt köztük: (1) a BEV-térnyerés tényleges mozgatórugói (akkumulátorár, töltőinfra, EU-szabályozás) pont azok, amikhez nincs hosszú történeti adatunk, ezért a backtest vak foltokkal dolgozik; (2) a tesztelt tényezők együtthatóinak nincs kimutatható előrejelző ereje. A p-értékek ráadásul optimisták: az állomány-részesedés éves változásai erősen autokorreláltak, így a független megfigyelések száma kisebb, mint n.