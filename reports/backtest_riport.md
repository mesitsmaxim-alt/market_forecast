# Backtesting — 2026-10-01

A `config/segments.json`-ban kézzel megadott érzékenységi együtthatók visszamérése valós, történeti adaton. **Csak 4 a 8 tényezőből tesztelhető** (finanszírozási költség, vásárlóerő, fogyasztói szándék, üzemanyagár — az utóbbi az Eurostat HICP-üzemanyagindexéből) — ehhez van elég hosszú, éves bontású valós idősorunk. A többi tényezőhöz (akkumulátorár, töltőinfra, EV-vám, CO2-szabályozás) nincs elég hosszú visszamenő adat a projektben, ezért ez a backtest **a modell egy részét, nem az egészét** validálja.

> **Módszertani megjegyzés:** a "megfigyelt piaci momentum" tag (`engine.py`) szándékosan KI van hagyva ebből a tesztből. A hajtás-momentum ma már az új autók hajtás szerinti részesedéséből jön (Eurostat, csak 2020-tól), nem az itt kimenetként használt KSH-állományból, de ugyanazt a piaci átrendeződést méri, így bevonása részben körkörös lenne, és a 2020 előtti évekre nincs is adata. A backtest tehát kifejezetten azt méri, van-e előrejelző ereje a forgatókönyv-tényezőknek ÖNMAGUKBAN, a nyers trendtől függetlenül.

## BEV vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.15
- **Hit rate** (előjel-egyezés): 61% (n=23 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.042 | +0.05367 | ✅ |
| 2004 | -0.106 | +0.09958 | ❌ |
| 2005 | -0.140 | +0.20019 | ❌ |
| 2006 | -0.101 | +0.07764 | ❌ |
| 2007 | -0.053 | -0.08751 | ✅ |
| 2008 | -0.026 | +0.16043 | ❌ |
| 2009 | +0.012 | -0.15153 | ❌ |
| 2010 | +0.099 | +0.42668 | ✅ |
| 2011 | +0.208 | +0.23890 | ✅ |
| 2012 | +0.309 | +0.19009 | ✅ |
| 2013 | +0.149 | +0.03821 | ✅ |
| 2014 | +0.099 | +0.04934 | ✅ |
| 2015 | +0.088 | -0.18551 | ❌ |
| 2016 | +0.139 | -0.09426 | ❌ |
| 2017 | +0.263 | +0.15806 | ✅ |
| 2018 | +0.357 | +0.16853 | ✅ |
| 2019 | +0.477 | +0.02203 | ✅ |
| 2020 | +0.915 | -0.14679 | ❌ |
| 2021 | +1.332 | +0.42286 | ✅ |
| 2022 | +1.417 | +0.14904 | ✅ |
| 2023 | +1.440 | +0.37461 | ✅ |
| 2024 | +1.968 | +0.08322 | ✅ |
| 2025 | +2.290 | -0.02885 | ❌ |

## Hibrid vs. ICE

- **Korreláció** (tényleges vs. előrejelzett irányú elmozdulás): +0.17
- **Hit rate** (előjel-egyezés): 52% (n=23 év, véletlen alapérték: 50%)

| Év | Tényleges Δ (pp) | Modell-pontszám Δ | Egyezik az irány? |
|---|---|---|---|
| 2003 | +0.064 | +0.05914 | ✅ |
| 2004 | -0.099 | +0.07901 | ❌ |
| 2005 | -0.141 | +0.14451 | ❌ |
| 2006 | -0.097 | +0.08633 | ❌ |
| 2007 | -0.045 | -0.03287 | ✅ |
| 2008 | -0.004 | +0.14276 | ❌ |
| 2009 | +0.026 | -0.10706 | ❌ |
| 2010 | +0.112 | +0.30969 | ✅ |
| 2011 | +0.228 | +0.20993 | ✅ |
| 2012 | +0.329 | +0.17151 | ✅ |
| 2013 | +0.171 | -0.00901 | ❌ |
| 2014 | +0.133 | -0.00787 | ❌ |
| 2015 | +0.137 | -0.16457 | ❌ |
| 2016 | +0.242 | -0.09062 | ❌ |
| 2017 | +0.429 | +0.11207 | ✅ |
| 2018 | +0.588 | +0.12111 | ✅ |
| 2019 | +0.774 | +0.01091 | ✅ |
| 2020 | +1.524 | -0.09123 | ❌ |
| 2021 | +2.122 | +0.33187 | ✅ |
| 2022 | +2.065 | +0.17081 | ✅ |
| 2023 | +2.114 | +0.30200 | ✅ |
| 2024 | +2.685 | +0.02619 | ✅ |
| 2025 | +2.923 | -0.02668 | ❌ |

## Értelmezés

- **BEV vs. ICE:** a találati arány (61%) érdemben jobb a véletlennél (50%); a korreláció (+0.15) gyenge, vagyis a pontszámok nagyságrendje részben követi a tényleges elmozdulást.
- **Hibrid vs. ICE:** a találati arány (52%) a véletlen szintjén van (50%) — az irányt ebben az összevetésben nem találja el megbízhatóan; a korreláció (+0.17) gyenge, vagyis a pontszámok nagyságrendje részben követi a tényleges elmozdulást.

Az érzékenységi együtthatók szakértői becslések; a gyenge eredmény egyik valószínű oka, hogy a BEV-térnyerés tényleges mozgatórugói (akkumulátorár, töltőinfra, EU-szabályozás) pont azok, amikhez nincs hosszú történeti adatunk — ez a backtest szükségszerűen vak foltokkal dolgozik.