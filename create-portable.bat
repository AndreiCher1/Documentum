@echo off
chcp 65001 >nul
title DocIntel - Build Portable UI
color 0A

echo ======================================================================
echo           Document Intelligence - Building Portable UI
echo ======================================================================
echo.

set "ROOT_DIR=%~dp0"
set "ELECTRON_DIR=%ROOT_DIR%document-intelligence\electron-app"

if not exist "%ELECTRON_DIR%" (
    echo [ERROR] electron-app directory not found: %ELECTRON_DIR%
    if not "%1"=="--no-pause" pause
    exit /b 1
)

cd /d "%ELECTRON_DIR%"

REM Check if Electron runtime is present
if not exist "%ELECTRON_DIR%\node_modules\electron\dist\electron.exe" (
    echo [1/2] Installing required Electron dependencies via npm...
    call npm install --no-audit --no-fund
    if errorlevel 1 (
        echo [ERROR] Failed to run npm install. Please ensure Node.js is installed.
        if not "%1"=="--no-pause" pause
        exit /b 1
    )
)

echo [2/2] Assembling standalone portable distribution...
node "scripts\build-portable.js"
if errorlevel 1 (
    echo [ERROR] Portable assembly failed.
    if not "%1"=="--no-pause" pause
    exit /b 1
)

echo.
echo Portable distribution is ready to use:
echo %ROOT_DIR%document-intelligence\portable-ui\DocIntel-UI.exe
echo.
if not "%1"=="--no-pause" pause
