#!/usr/bin/env sh
# Leitstand starten: richtet bei Bedarf die Umgebung ein und öffnet die Oberfläche.
# Aufruf: ./leitstand.sh [--port 9000] [--no-browser]
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Erstelle virtuelle Umgebung und installiere Abhängigkeiten ..."
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi

exec .venv/bin/python panel.py "$@"
