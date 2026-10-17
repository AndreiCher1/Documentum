@echo off
title DocIntel - Start Background Servers
color 0B

echo ======================================================================
echo           Document Intelligence - Starting Backend Servers
echo ======================================================================
echo.

set "BASE_DIR=%~dp0"
set "AI_DIR=%BASE_DIR%ai-service"
set "JAVA_DIR=%BASE_DIR%java-backend"

echo [1/2] Starting Python AI Service (port 8000)...
start "DocIntel: Python AI Service (Port 8000)" cmd.exe /k "cd /d "%AI_DIR%" && if exist "venv\Scripts\python.exe" ( echo [OK] Using virtual environment venv... && "venv\Scripts\python.exe" run.py ) else ( echo [!] venv not found, using system python... && python run.py )"

echo [2/2] Starting Java Spring Boot Backend (port 8085)...
start "DocIntel: Java Backend (Port 8085)" cmd.exe /k "cd /d "%JAVA_DIR%" && if exist "target\document-intelligence-0.1.0.jar" ( echo [OK] Launching packaged JAR... && java -jar target\document-intelligence-0.1.0.jar ) else ( echo [!] JAR not found, launching via Maven... && mvn.cmd spring-boot:run )"

echo.
echo ======================================================================
echo Server console windows have been opened!
echo Please wait 10-15 seconds for ML models and database to initialize.
echo ======================================================================
echo.
pause
