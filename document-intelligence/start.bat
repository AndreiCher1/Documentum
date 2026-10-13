@echo off
chcp 65001 >nul
title Document Intelligence - Запуск системы
color 0B

echo ======================================================================
echo           📄 DOCUMENT INTELLIGENCE - СИСТЕМА АНАЛИЗА ДОКУМЕНТОВ
echo ======================================================================
echo.

set "ROOT_DIR=%~dp0"
set "AI_DIR=%ROOT_DIR%ai-service"
set "JAVA_DIR=%ROOT_DIR%java-backend"
set "ELECTRON_DIR=%ROOT_DIR%electron-app"

:: 1. Запуск Python AI Service
echo [1/3] Запуск Python AI Service (PaddleOCR на порту 8000)...
if exist "%AI_DIR%\venv\Scripts\python.exe" (
    start "DocIntel: AI Service (port 8000)" /min cmd /c "cd /d ""%AI_DIR%"" && venv\Scripts\python.exe run.py"
) else (
    start "DocIntel: AI Service (port 8000)" /min cmd /c "cd /d ""%AI_DIR%"" && python run.py"
)

:: 2. Запуск Java Spring Boot Backend
echo [2/3] Запуск Java Backend (Spring Boot на порту 8085)...
if exist "%JAVA_DIR%\target\document-intelligence-0.1.0.jar" (
    start "DocIntel: Java Backend (port 8085)" /min cmd /c "cd /d ""%JAVA_DIR%"" && java -jar target\document-intelligence-0.1.0.jar"
) else (
    start "DocIntel: Java Backend (port 8085)" /min cmd /c "cd /d ""%JAVA_DIR%"" && mvn.cmd spring-boot:run"
)

:: 3. Ожидание запуска сервисов
echo.
echo Ожидание инициализации backend-сервисов...
set "HEALTHY=0"
for /L %%i in (1,1,30) do (
    powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://localhost:8085/api/health' -TimeoutSec 2; if ($r.status -eq 'healthy') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "HEALTHY=1"
        goto :services_ready
    )
    <nul set /p =.
    timeout /t 1 /nobreak >nul
)

:services_ready
echo.
if "%HEALTHY%"=="1" (
    echo [✓] Все сервисы запущены и готовы к работе!
) else (
    echo [!] Серверы еще инициализируются, запускаем интерфейс...
)

:: 4. Запуск Electron UI
echo [3/3] Открытие интерфейса Electron...
cd /d "%ELECTRON_DIR%"
npm start

echo.
echo Приложение закрыто. Для полной остановки фоновых сервисов запустите stop.bat.
pause

