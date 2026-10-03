@echo off
rem Leitstand starten: richtet bei Bedarf die Umgebung ein und oeffnet die Oberflaeche.
rem Aufruf: leitstand.cmd [--port 9000] [--no-browser]
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Erstelle virtuelle Umgebung und installiere Abhaengigkeiten ...
  python -m venv .venv || goto :fehler
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :fehler
)

".venv\Scripts\python.exe" panel.py %*
exit /b %errorlevel%

:fehler
echo Einrichtung fehlgeschlagen - laeuft Python im PATH?
exit /b 1
