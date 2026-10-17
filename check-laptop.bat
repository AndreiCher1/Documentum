@echo off
title DocIntel - Laptop Servers Diagnostic
color 0F

echo ======================================================================
echo           DocIntel: Server Diagnostic and Launcher
echo ======================================================================
echo.

set "ROOT_DIR=%~dp0"
set "AI_DIR=%ROOT_DIR%document-intelligence\ai-service"
set "JAVA_DIR=%ROOT_DIR%document-intelligence\java-backend"
set "ELECTRON_DIR=%ROOT_DIR%document-intelligence\electron-app"

REM 1. Check Java
echo [1/4] Checking Java runtime:
where.exe java >nul 2>&1
if %errorlevel% equ 0 (
    echo     [OK] Java is installed in PATH.
) else (
    echo     [X] Java is NOT found in PATH.
    echo         Install Java 17 or 21 JDK to run backend.
)
echo.

REM 2. Check Python
echo [2/4] Checking Python runtime:
where.exe python >nul 2>&1
if %errorlevel% equ 0 (
    echo     [OK] Python is installed in PATH.
) else (
    echo     [X] Python is NOT found in PATH.
    echo         Install Python 3.10-3.12 to run AI service.
)
echo.

REM 3. Check project builds
echo [3/4] Checking components:
if exist "%JAVA_DIR%\target\document-intelligence-0.1.0.jar" (
    echo     [OK] Java JAR ready: target\document-intelligence-0.1.0.jar
) else (
    echo     [!] Java JAR not found in target folder.
)

if exist "%AI_DIR%\venv\Scripts\python.exe" (
    echo     [OK] Python venv ready: ai-service\venv\
) else (
    echo     [!] Python venv not found. System python will be used.
)
echo.

REM 4. Check active ports
echo [4/4] Checking port status:
powershell -NoProfile -Command "$c8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($c8000) { Write-Host '    [OK] Python AI Service: ONLINE (port 8000)' -ForegroundColor Green } else { Write-Host '    [-] Python AI Service: OFFLINE (port 8000 free)' -ForegroundColor Yellow }"

powershell -NoProfile -Command "$c8085 = Get-NetTCPConnection -LocalPort 8085 -State Listen -ErrorAction SilentlyContinue; if ($c8085) { Write-Host '    [OK] Java Backend API: ONLINE (port 8085)' -ForegroundColor Green } else { Write-Host '    [-] Java Backend API: OFFLINE (port 8085 free)' -ForegroundColor Yellow }"
echo.

echo ======================================================================
echo ACTIONS:
echo   1. Start both servers in visible windows with live logs
echo   2. Stop all running DocIntel servers (stop.bat)
echo   3. Launch full application (start.bat)
echo   0. Exit
echo ======================================================================
if "%1"=="--check-only" goto :eof

choice /c 1230 /n /m "Select option (1, 2, 3 or 0): "

if errorlevel 4 goto :eof
if errorlevel 3 (
    call "%ROOT_DIR%start.bat"
    goto :eof
)
if errorlevel 2 (
    call "%ROOT_DIR%stop.bat"
    pause
    goto :eof
)
if errorlevel 1 (
    call "%ROOT_DIR%start-servers.bat"
    goto :eof
)
