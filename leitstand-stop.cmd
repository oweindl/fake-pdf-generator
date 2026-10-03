@echo off
rem Leitstand beenden - auch wenn er ohne Fenster (pythonw) gestartet wurde.
rem Aufruf: leitstand-stop.cmd [Port]    (Standard 8765)
setlocal
set PORT=%1
if "%PORT%"=="" set PORT=8765

powershell -NoProfile -Command ^
  "$p = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($p) { $p | ForEach-Object { Stop-Process -Id $_ -Force }; Write-Host ('Leitstand auf Port %PORT% beendet (PID ' + ($p -join ', ') + ')') } else { Write-Host ('Kein Leitstand auf Port %PORT% gefunden.') }"
exit /b %errorlevel%
