@echo off
title Document Intelligence - Stopping Services
echo ======================================================================
echo           STOPPING DOCUMENT INTELLIGENCE SERVICES
echo ======================================================================
echo.

powershell -NoProfile -Command "$ports = @(8000, 8085); foreach ($port in $ports) { try { $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue; if ($conns) { $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($p in $pids) { if ($p -gt 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Write-Host ('[OK] Port ' + $port + ' freed (PID: ' + $p + ')') -ForegroundColor Green } } } else { Write-Host ('[-] Port ' + $port + ' already free') -ForegroundColor DarkGray } } catch {} }; Get-Process electron,DocIntel,DocIntel-UI -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Write-Host '[OK] UI processes terminated' -ForegroundColor Green"

echo.
echo All Document Intelligence services stopped.
ping -n 2 127.0.0.1 >nul
