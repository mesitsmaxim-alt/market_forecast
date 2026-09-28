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

  echo "--- Dashboard adat frissítése ---"
  "$PYTHON" dashboard/build_dashboard.py

  echo "--- Backtesting ---"
  "$PYTHON" backtest.py

  echo "--- Digest ---"
  NOTIF_TEXT="$("$PYTHON" digest_report.py)"
  echo "$NOTIF_TEXT"

  echo "=== Pipeline kész: $(date) ==="
} >> "$LOG_FILE" 2>&1

# Az értesítést szándékosan a naplózott blokkon KÍVÜL küldjük, hogy egy
# esetleges osascript-hiba (pl. nincs bejelentkezett GUI-munkamenet) ne
# dobja hibára a teljes pipeline-t (set -e), és a naplóba is bekerüljön
# a digest-szöveg a fenti "echo $NOTIF_TEXT" sorból.
osascript -e "display notification \"${NOTIF_TEXT//\"/\\\"}\" with title \"Autópiaci előrejelző frissült\" subtitle \"$(date +%Y-%m-%d)\"" 2>/dev/null || true

echo "Log: $LOG_FILE"
