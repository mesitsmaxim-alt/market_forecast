#!/bin/bash
# Teljes piaci előrejelző pipeline: friss adat letöltése, kalibráció, riportok.
# Ütemezve fut (launchd), de kézzel is futtatható: ./run_pipeline.sh

set -euo pipefail
cd "$(dirname "$0")"

PYTHON=python3
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run_$(date +%Y-%m-%d_%H%M%S).log"

{
  echo "=== Piaci előrejelző pipeline indul: $(date) ==="

  echo "--- Adatletöltés ---"
  "$PYTHON" fetchers/fetch_jarmuallomany.py
  "$PYTHON" fetchers/fetch_uj_hajtas.py
  "$PYTHON" fetchers/fetch_uzemanyag_elo.py
  "$PYTHON" fetchers/fetch_uzemanyagar.py
  "$PYTHON" fetchers/fetch_makro.py
  "$PYTHON" fetchers/fetch_forgalomba.py
  "$PYTHON" fetchers/fetch_szentiment.py
  "$PYTHON" fetchers/fetch_realjovedelem.py
  "$PYTHON" fetchers/fetch_hirek.py

  echo "--- Kalibráció ---"
  "$PYTHON" calibrate_factors.py

  echo "--- Riportok generálása ---"
  "$PYTHON" generate_report.py --all-scenarios
  "$PYTHON" segment_report.py
  "$PYTHON" fuel_report.py
  "$PYTHON" makro_report.py
  "$PYTHON" toltoinfra_report.py
  "$PYTHON" forgalomba_report.py
  "$PYTHON" szentiment_report.py
  "$PYTHON" realjovedelem_report.py
  "$PYTHON" hirek_report.py

  # A backtest a dashboard ELŐTT fut: a dashboard módszertani blokkja a
  # data/backtest.json-t olvassa, így a mostani futás eredményét mutatja.
  echo "--- Backtesting ---"
  "$PYTHON" backtest.py

  echo "--- Dashboard adat frissítése ---"
  "$PYTHON" dashboard/build_dashboard.py

  echo "--- Digest ---"
  NOTIF_TEXT="$("$PYTHON" digest_report.py)"
  echo "$NOTIF_TEXT"

  echo "=== Pipeline kész: $(date) ==="
} >> "$LOG_FILE" 2>&1

# Auto-commit + push: csak sikeres pipeline után fut (a set -e egy hibás
# lépésnél már korábban kiléptet). Szándékosan nem dobja hibára a futást,
# ha a push nem sikerül (pl. nincs hálózat) — a commit ilyenkor helyben
# megmarad, és a következő futás push-a viszi fel.
{
  echo "--- Git auto-commit ---"
  # Csak a pipeline által GENERÁLT fájlokat vesszük fel - egy félkész,
  # még nem commitolt kódmódosítás így sosem kerül be egy "Havi
  # pipeline-futás" commitba.
  git add -- data/ reports/ config/factors.json dashboard/dashboard.html dashboard/dashboard_data.json
  if git diff --cached --quiet; then
    echo "Nincs változás, nincs commit."
  else
    git commit -q -m "Havi pipeline-futás: $(date +%Y-%m-%d)" \
      -m "Automatikus commit a run_pipeline.sh-ból (adatfrissítés, kalibráció, riportok, dashboard)." \
      && git log --oneline -1
  fi
  git push -q origin main && echo "Push kész." || echo "FIGYELEM: a push nem sikerült, a commit helyben megmaradt."
} >> "$LOG_FILE" 2>&1 || true

# Az értesítést szándékosan a naplózott blokkon KÍVÜL küldjük, hogy egy
# esetleges osascript-hiba (pl. nincs bejelentkezett GUI-munkamenet) ne
# dobja hibára a teljes pipeline-t (set -e), és a naplóba is bekerüljön
# a digest-szöveg a fenti "echo $NOTIF_TEXT" sorból.
osascript -e "display notification \"${NOTIF_TEXT//\"/\\\"}\" with title \"Autópiaci előrejelző frissült\" subtitle \"$(date +%Y-%m-%d)\"" 2>/dev/null || true

echo "Log: $LOG_FILE"
