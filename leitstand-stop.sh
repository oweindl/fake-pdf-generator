#!/usr/bin/env sh
# Leitstand beenden (Linux/macOS): findet panel.py und stoppt die Prozesse.
# Aufruf: ./leitstand-stop.sh
set -e
cd "$(dirname "$0")"

if pkill -f "panel.py" 2>/dev/null; then
  echo "Leitstand beendet."
else
  echo "Kein laufender Leitstand gefunden."
fi
