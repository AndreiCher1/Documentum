@echo off
title Document Intelligence - Starting System
color 0B

echo ======================================================================
echo           Document Intelligence Platform - DocIntel
echo ======================================================================
echo.

set "ROOT_DIR=%~dp0"
set "AI_DIR=%ROOT_DIR%ai-service"
set "JAVA_DIR=%ROOT_DIR%java-backend"
set "ELECTRON_DIR=%ROOT_DIR%electron-app"

REM 1. Check and launch Python AI Service
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [1/3] Python AI Service is already active on port 8000.
    goto :check_java
)

echo [1/3] Starting Python AI Service on port 8000...
if exist "%AI_DIR%\venv\Scripts\pythonw.exe" (
    powershell -NoProfile -Command "Start-Process -FilePath '%AI_DIR%\venv\Scripts\pythonw.exe' -ArgumentList 'run.py' -WorkingDirectory '%AI_DIR%' -WindowStyle Hidden"
) else (
    powershell -NoProfile -Command "Start-Process -FilePath 'pythonw.exe' -ArgumentList 'run.py' -WorkingDirectory '%AI_DIR%' -WindowStyle Hidden"
)

:check_java
REM 2. Check and launch Java Spring Boot Backend
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8085 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [2/3] Java Backend is already active on port 8085.
    goto :wait_services
)

echo [2/3] Starting Java Backend on port 8085...
if exist "%JAVA_DIR%\target\document-intelligence-0.1.0.jar" (
    powershell -NoProfile -Command "Start-Process -FilePath 'javaw.exe' -ArgumentList '-jar', 'target\document-intelligence-0.1.0.jar' -WorkingDirectory '%JAVA_DIR%' -WindowStyle Hidden"
) else (
    powershell -NoProfile -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'mvn.cmd spring-boot:run' -WorkingDirectory '%JAVA_DIR%' -WindowStyle Hidden"
)

:wait_services
REM 3. Wait for backend services to be healthy
echo.
echo Waiting for backend services to become ready...
set "HEALTHY=0"
set "WAIT_COUNT=0"

:wait_loop
powershell -NoProfile -Command "$r = try { (Invoke-RestMethod 'http://localhost:8085/api/health' -TimeoutSec 2).status } catch { '' }; if ($r -eq 'healthy') { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    set "HEALTHY=1"
    goto :services_ready
)
<nul set /p =.
ping -n 2 127.0.0.1 >nul
set /a WAIT_COUNT+=1
if %WAIT_COUNT% lss 30 goto :wait_loop

:services_ready
echo.
if "%HEALTHY%"=="1" (
    echo [OK] All backend services are ready!
) else (
    echo [!] Backend is still initializing, opening interface...
)

REM 4. Launch Electron UI (Multi-level resilient launcher)
echo [3/3] Opening user interface...
set ELECTRON_RUN_AS_NODE=
set "UI_LAUNCHED=0"

REM 4.1. Check if standalone portable build exists (fastest, 0 dependencies)
if exist "%ROOT_DIR%portable-ui\DocIntel-UI.exe" (
    echo [UI] Starting portable Electron interface (DocIntel-UI.exe)...
    powershell -NoProfile -Command "Start-Process -FilePath '%ROOT_DIR%portable-ui\DocIntel-UI.exe' -WorkingDirectory '%ROOT_DIR%portable-ui'"
    set "UI_LAUNCHED=1"
    goto :monitor_app
)

REM 4.2. Check if local Electron binary is present in node_modules
if exist "%ELECTRON_DIR%\node_modules\electron\dist\electron.exe" (
    echo [UI] Starting Electron interface from local binary...
    powershell -NoProfile -Command "Start-Process -FilePath '%ELECTRON_DIR%\node_modules\electron\dist\electron.exe' -ArgumentList '%ELECTRON_DIR%' -WorkingDirectory '%ELECTRON_DIR%'"
    set "UI_LAUNCHED=1"
    goto :monitor_app
)

REM 4.3. Fresh repository clone detected: auto-install dependencies if npm is available
echo [UI] First launch detected: installing Electron dependencies (npm install)...
cd /d "%ELECTRON_DIR%"
call npm install --no-audit --no-fund
if exist "%ELECTRON_DIR%\node_modules\electron\dist\electron.exe" (
    echo [UI] Dependencies installed successfully, starting Electron...
    powershell -NoProfile -Command "Start-Process -FilePath '%ELECTRON_DIR%\node_modules\electron\dist\electron.exe' -ArgumentList '%ELECTRON_DIR%' -WorkingDirectory '%ELECTRON_DIR%'"
    set "UI_LAUNCHED=1"
    goto :monitor_app
)

REM 4.4. Try npm start if electron was installed via system packages
where.exe electron >nul 2>&1
if not errorlevel 1 (
    echo [UI] Starting via system electron...
    call npm start
    set "UI_LAUNCHED=1"
    goto :monitor_app
)

REM 4.5. Fallback: If neither Electron nor Node.js is installed, open in browser / Edge App Mode
echo [!] Electron / Node.js not detected on this system.
echo [!] Launching DocIntel in Web App window mode...
start "" msedge.exe --app="http://localhost:8085" >nul 2>&1
if not errorlevel 1 (
    set "UI_LAUNCHED=1"
    goto :monitor_app
)
start "" "http://localhost:8085"
set "UI_LAUNCHED=1"

:monitor_app
REM 5. Keep services running while UI window is open
ping -n 3 127.0.0.1 >nul
:wait_ui_closed
powershell -NoProfile -Command "if (Get-Process electron,DocIntel-UI,DocIntel -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    ping -n 3 127.0.0.1 >nul
    goto :wait_ui_closed
)

echo.
echo Stopping background services...
call "%ROOT_DIR%stop.bat"
exit /b 0
