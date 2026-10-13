@echo off
chcp 65001 >nul
title Document Intelligence - Остановка системы
echo ======================================================================
echo           🛑 ОСТАНОВКА СЕРВИСОВ DOCUMENT INTELLIGENCE
echo ======================================================================
echo.

powershell -NoProfile -Command "$ports = @(8000, 8085); foreach ($port in $ports) { try { $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue; if ($conns) { $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($p in $pids) { if ($p -gt 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Write-Host ('[✓] Освобожден порт ' + $port + ' (PID: ' + $p + ')') -ForegroundColor Green } } } else { Write-Host ('[-] Порт ' + $port + ' свободен') -ForegroundColor DarkGray } } catch {} }; Get-Process electron,DocIntel -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Write-Host '[✓] Процессы интерфейса закрыты' -ForegroundColor Green"

echo.
echo Все сервисы Document Intelligence остановлены.
ping -n 2 127.0.0.1 >nul
