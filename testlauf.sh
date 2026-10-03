#!/usr/bin/env sh
# Testlauf: richtet bei Bedarf die Umgebung ein und fährt alle Betriebsarten durch.
# Aufruf: ./testlauf.sh [--live] [--out ORDNER] [--keep]
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Erstelle virtuelle Umgebung und installiere Abhängigkeiten ..."
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi

exec .venv/bin/python testrun.py "$@"
