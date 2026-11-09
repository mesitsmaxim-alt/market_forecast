# Validációs audit (újra) — 2026-11-05

Utólagos audit a reggeli audit (`validacio_audit_2026-11-05.md`) után végrehajtott változtatásokra:
`9d1a633` (nulla alap 3 tényezőnél, töltőinfra-vetítés 4 negyedéves ablakkal) és `a1f0e0b`
(semleges tartomány és rangsor-küszöb a dashboard szövegeiben, forgalomba-vetítés 2 negyedévre).
Hét ellenőrző ágens futott, projektfájlt egyik sem módosított.

## Végső ítélet: **WARN** — publikálható

CRITICAL nincs. A reggeli két CRITICAL→WARN pontból a szentiment-perzisztencia megszűnt, a
hibrid/elektromos sáv dokumentált korlát maradt. Egy olvasót érintő szövegprobléma van (A „Mi
változott?” blokk, lásd lent), ezt publikálás előtt érdemes rendbe tenni.

| Terület | Ítélet | Ágensek |
|---|---|---|
| A — Modell | WARN | invariant-checker PASS, calibration-auditor PASS, stats-reviewer WARN |
| B — Predikciók | WARN | prediction-tracker WARN, source-verifier PASS |
| C — Feltételezések | WARN | assumption-stress-tester WARN, plausibility-reviewer WARN |

## A — Modell

- **Invariánsok:** minden ellenőrzés sikeres. Az alap = 0 tényezőknél a sávellenőrzés tartalmilag
  is fut.
- **Kalibráció:** mind a 8 tényező alapja és sávja független újraszámolással egyezik (≤0,05
  eltérés). Nincs `-0.0`. 14/14 szintetikus egységteszt sikeres (`compute_segments`, momentum-sapkák,
  `classify`-küszöbök, `linreg_forecast`, `forecast_card` ablakozás).
- **Nulla alap (olaj, kamat, szentiment):** statisztikailag megalapozott. A walk-forward MAE-k
  pontosan reprodukálódtak, és a teljes történeti mintán is tartanak (trend / nulla: üzemanyag
  13,2 / 9,9; szentiment 14,9 / 9,3; alapkamat 2,9 / 2,0). 12 hónapos blokk-bootstrap: annak
  valószínűsége, hogy a trend nem rosszabb a nullánál, 0,000–0,03. A szentimentnél szerkezeti
  visszatérés az átlaghoz (béta −0,49). A k = 0 nem hangolt paraméter. A k < 0 hangolás lenne,
  ezért nem javasolt.

## B — Predikciók

- **Töltőinfra-kártya (window = 4):** h = 2–4-nél jobb a random walknál (pl. h = 4: 687 vs 799),
  h = 1-nél kicsit rosszabb (269 vs 236). A múltbeli hibákból épített sáv 73–85%-ot fed. A 8
  negyedéves ablakhoz képest a javulás nem szignifikáns (előjelpróba p = 0,48–1,0), és a w5–w6
  változatok sem különböztethetők meg tőle. Megtartható, de nem „jobb modell”, csak óvatosabb.
- **Forgalomba-kártya (steps = 2, window = 6):** mindkét lépésen jobb a random walknál (3116 vs
  3670, 4567 vs 5627). A 4 lépésről 2-re rövidítés indokolt: a régi 3–4. lépés sávja csak 30–33%-ot
  fedett. A w5 és a w6 nem különböztethető meg, kicsi a minta (7–12 vágás).
- **Szezonális kockázat:** a II.→III. negyedévi változás mind a 4 évben negatív volt (−1,7…−7,1%).
  A kártya a 2026 III. negyedévre ~0%-ot vetít, a pont 2–6%-kal túlbecsülhet. Az alsó sáv lefedi.
- **Hibrid/elektromos részesedés-kártya:** a sáv továbbra is 11–14%-ot fed. Dokumentált korlát, a
  pont jobb a random walknál.
- **Kamat ±σ sáv:** az utolsó 5 évben 40%-os lefedettség (alapkamat-sokkok). Nem blokkoló.
- **Források:** a top 20 modell, az összpiac (129 949) és az előző havi 100 sor egyezik a
  jarmuipar.hu cikkekkel. A duplikált 9. hely javítása és a duplikált nevek párosítása helyes. A kézi
  forrásoknál (akkuár, EV-vám, CO2) nincs ismert újdonság. A webes keresés nem dátumszűrt, ez nem
  bizonyítja, hogy nincs változás.
- **Snapshotok:** 6 független nap. A BEV > PHEV > HEV > ICE sorrend mindegyiken azonos. Ex-post
  értékelés a 2026 III. negyedéves KSH-adat után lehetséges.

## C — Feltételezések

- **Robusztusság:** a hajtásszintű előjelek 500 véletlen perturbációban 100%-ban stabilak (seed 42,
  együtthatónként ±0,15). A BEV „Erős növekedés” is stabil.
- **A dashboard új szabályai alátámasztottak:**
  - A márkarangsor csak 32%-ban stabil. A rangsor-stabilitás 1 pont alatti különbségnél 62–63%,
    1,36 pontnál 82%. A 2 pontos küszöb reális alsó határ.
  - A piacsúlyozott értékek 99–100%-ban a ±5-ös semleges sávban maradnak. Kivétel a budget (−4,2),
    amely 28%-ban −5 alá kerülne.
- **A co2_regulation dominál:** a tornado első 8 helye. Az ICE −9,4 pontjából −6,5 innen jön, és ez
  egy kézi becslés. Nélküle az ICE „Stagnálás”, a BEV „Növekedés”.
- **A HEV pontszáma momentum:** a 8,0 pontból kb. 6,4 a megfigyelt lendület (új autók részesedése
  és forgalomba helyezés). Momentum nélkül a HEV „Stagnálás”.
- **A márka-„Növekedés” fele regisztrációs momentum:** a tömeggyártó és a prémium márka
  `REG_MOMENTUM_WEIGHT = 0` mellett „Stagnálás” lenne.
- **Szövegek:** a jelenlegi adatokkal rekonstruált hajtás-, márka- és évjárat-mondatok igazak. A HEV
  és a PHEV közötti 1,4 pontos különbséget a szöveg helyesen nem rangsorolja. A sávdiagram sorrendje
  vizuálisan mégis rangsor.

## Triázs — teendők fontossági sorrendben

1. **[WARN, olvasót érint] „Mi változott?” blokk:** 6 címkeváltást mutat piaci változásként (HEV
   16,8 → 8,0, BEV 33,1 → 19,5), pedig szinte teljesen a mai módszertani váltás (nulla alap)
   okozza. A piac alig mozdult: a benzin 636 → 633 Ft/l. Javaslat: módszertani-változás jelölés a
   `changes` blokkban és a Történet fülön, a snapshot-sor törésénél.
2. **[WARN] charging_infra k = 1 következetlen mérce:** ugyanazzal a walk-forward mércével a
   töltőinfra YoY-n a k = 1 a legrosszabb (MAE 39,9 vs k = 0: 30,3; n = 18). A prediction-tracker
   szerint viszont az utolsó 8 negyedévben a k = 1 jobb (17,4 vs 22,3), mert a korai kis bázisú
   növekedés más rezsim.
   - Döntés: nem sürgős, de a CLAUDE.md-ben a „persistence was defensible there” állítás nem áll
     meg.
   - Javaslat: újramérés az utolsó 12 negyedévre új EAFO-adat után, vagy tudatos kivételként
     dokumentálni.
3. **[WARN] HEV és márka-momentum:** a dashboard szövege jelezhetné, hogy a HEV és a tömeggyártó,
   illetve prémium márka „Növekedés” címkéje a már megfigyelt trendből ered, nem a forgatókönyv
   tényezőiből.
4. **[INFO] Ablakválasztás kommunikációja:** a CLAUDE.md a forgalomba 6 negyedéves trendjét „a
   legjobb”-nak nevezi. A stats-reviewer szerint ez a w5-től nem különböztethető meg (és
   ugyanazon az adaton szelektáltak). Pontosítandó: „a legjobbak között, kis minta”.
5. **[INFO] Forgalomba III. negyedéves szezonális gyengülés:** megjegyzés a CLAUDE.md-be vagy a
   kártyaszövegbe.
6. **[INFO] Apróságok:**
   - Opcionális `band > 0` invariáns.
   - Az `apply_persistence()` indoklás-szövege k-független, 0 < k < 1 esetén átírandó.
   - Az üzemanyagár-összehasonlítás egy még tartó hétre esik, ez csak a megjegyzés szövegét
     érinti.
   - A pesszimista/optimista forgatókönyv stressz-tesztje a következő auditra marad.

## Feloldott ellentmondás az ágensek között

A töltőinfra perzisztenciáját illetően (2. pont) a stats-reviewer a teljes mintán k = 0-t, a
prediction-tracker az utolsó 8 negyedéven k = 1-et talált jobbnak. Mindkettő kis mintán (n = 8–18)
mér, egyik sem szignifikáns. Ítélet: WARN, nincs azonnali változtatás, újramérés új adattal.
