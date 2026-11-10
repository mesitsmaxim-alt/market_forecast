# Stressz-teszt: pesszimista és optimista forgatókönyv — 2026-11-10

A 2026-11-05-i audit csak az alap forgatókönyvet perturbálta. Ez a teszt mindhárom
forgatókönyvre megismétli: a hajtás- és márkakategória-érzékenységek mindegyikét
U(−0,15; +0,15) eltolással, 500 véletlen futásban (seed 42), memóriában (a config nem
változott). Hajtás-összesítő = a 12 szegmens egyszerű átlaga, pontban.

| Forgatókönyv | Hajtás | Pont | Címke | Előjel stabil | Címke stabil | 5–95% tartomány |
|---|---|---|---|---|---|---|
| pesszimista | belső égésű | −5,2 | Visszaesés | 100% | 56% | −7,5 … −2,7 |
| pesszimista | hibrid | −4,0 | Stagnálás | 99,6% | 75% | −6,3 … −1,4 |
| pesszimista | plug-in hibrid | −8,7 | Visszaesés | 100% | 100% | −11,0 … −6,3 |
| pesszimista | tisztán elektromos | −13,7 | Visszaesés | 100% | 83% | −16,0 … −11,3 |
| alap | belső égésű | −9,4 | Visszaesés | 100% | 100% | −11,3 … −7,5 |
| alap | hibrid | +8,0 | Növekedés | 100% | 100% | +6,2 … +9,7 |
| alap | plug-in hibrid | +9,4 | Növekedés | 100% | 100% | +7,5 … +11,3 |
| alap | tisztán elektromos | +19,5 | Erős növekedés | 100% | 100% | +17,7 … +21,4 |
| optimista | belső égésű | −13,7 | Visszaesés | 100% | 72% | −17,6 … −9,8 |
| optimista | hibrid | +20,1 | Erős növekedés | 100% | 99% | +16,2 … +23,6 |
| optimista | plug-in hibrid | +27,5 | Erős növekedés | 100% | 100% | +24,0 … +31,1 |
| optimista | tisztán elektromos | +52,7 | Erős növekedés | 100% | 100% | +49,1 … +56,2 |

## Következtetés

- **Előjelek:** mindhárom forgatókönyvben stabilak (99,6–100%). A forgatókönyv-váltó által
  mutatott irányok nem a véletlen együttható-választáson múlnak.
- **Címkék a küszöbök közelében:** a pesszimista belső égésű (−5,2, a −5 küszöbön) és hibrid
  (−4,0) címkéje bizonytalan, ahogy az optimista belső égésűé (−13,7, a −15 közelében) is.
  Ezeknél a pont számít, nem a címke. A dashboard a pontot mindig kiírja, és 2 pont alatti
  különbséget nem rangsorol (a pesszimista belső égésű és hibrid között 1,2 pont van).
- **Sorrend:** alapban és optimistában BEV > PHEV > HEV > ICE. Pesszimistában minden hajtás
  negatív, és a villamosított hajtások esnek a legjobban — ez a forgatókönyv definíciójából
  következik (a tengely az EV-adaptáció), nem hiba.
- Nincs teendő a modellen. A címke-bizonytalanságot a meglévő szabályok (pont kiírva,
  CLOSE_PTS = 2) kezelik.
