@echo off
chcp 65001 >nul
title Document Intelligence - Остановка системы
color 0C

echo ======================================================================
echo           🛑 ОСТАНОВКА СЕРВИСОВ DOCUMENT INTELLIGENCE
echo ======================================================================
echo.

powershell -NoProfile -Command "
$ports = @(8000, 8085)
foreach ($port in $ports) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($conns) {
            $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($p in $pids) {
                if ($p -gt 0) {
                    try {
                        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
                        $pname = if ($proc) { $proc.ProcessName } else { 'Process' }
                        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                        Write-Host ('[✓] Освобожден порт ' + $port + ' (остановлен ' + $pname + ' PID: ' + $p + ')') -ForegroundColor Green
                    } catch {}
                }
            }
        } else {
            Write-Host ('[-] Порт ' + $port + ' уже свободен') -ForegroundColor DarkGray
        }
    } catch {}
}

# Остановка процессов Electron
$electronProcs = Get-Process electron -ErrorAction SilentlyContinue
if ($electronProcs) {
    $electronProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host '[✓] Процессы Electron закрыты' -ForegroundColor Green
}
"

echo.
echo Все сервисы Document Intelligence остановлены.
timeout /t 3 >nul

