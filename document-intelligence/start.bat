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

REM 4. Launch Electron UI
echo [3/3] Opening Electron user interface...
cd /d "%ELECTRON_DIR%"
set ELECTRON_RUN_AS_NODE=
call npm start

REM 5. Shutdown background services when no Electron windows remain
powershell -NoProfile -Command "if (Get-Process electron -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Stopping background services...
    call "%ROOT_DIR%stop.bat"
)
exit /b 0
