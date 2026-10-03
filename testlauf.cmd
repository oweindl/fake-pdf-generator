@echo off
rem Testlauf: richtet bei Bedarf die Umgebung ein und fährt alle Betriebsarten durch.
rem Aufruf: testlauf.cmd            (ohne echten Mailversand)
rem          testlauf.cmd --live    (mit SMTP-Anmeldung und einer Testmail)
rem          testlauf.cmd --out D:\test --keep
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Erstelle virtuelle Umgebung und installiere Abhaengigkeiten ...
  python -m venv .venv || goto :fehler
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :fehler
)

".venv\Scripts\python.exe" testrun.py %*
exit /b %errorlevel%

:fehler
echo Einrichtung fehlgeschlagen - laeuft Python im PATH?
exit /b 1
