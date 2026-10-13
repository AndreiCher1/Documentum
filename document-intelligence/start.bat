@echo off
chcp 65001 >nul
title Document Intelligence - Запуск системы
color 0B

echo ======================================================================
echo           ДокументИнтеллект - Document Intelligence Platform
echo ======================================================================
echo.

set "ROOT_DIR=%~dp0"
set "AI_DIR=%ROOT_DIR%ai-service"
set "JAVA_DIR=%ROOT_DIR%java-backend"
set "ELECTRON_DIR=%ROOT_DIR%electron-app"

:: 1. Проверка и запуск Python AI Service
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [1/3] Python AI Service уже активен на порту 8000.
    goto :check_java
)

echo [1/3] Запуск Python AI Service [PaddleOCR на порту 8000]...
if exist "%AI_DIR%\venv\Scripts\pythonw.exe" (
    powershell -NoProfile -Command "Start-Process -FilePath '%AI_DIR%\venv\Scripts\pythonw.exe' -ArgumentList 'run.py' -WorkingDirectory '%AI_DIR%' -WindowStyle Hidden"
) else (
    powershell -NoProfile -Command "Start-Process -FilePath 'pythonw.exe' -ArgumentList 'run.py' -WorkingDirectory '%AI_DIR%' -WindowStyle Hidden"
)

:check_java
:: 2. Проверка и запуск Java Spring Boot Backend
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8085 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [2/3] Java Backend уже активен на порту 8085.
    goto :wait_services
)

echo [2/3] Запуск Java Backend [Spring Boot на порту 8085]...
if exist "%JAVA_DIR%\target\document-intelligence-0.1.0.jar" (
    powershell -NoProfile -Command "Start-Process -FilePath 'javaw.exe' -ArgumentList '-jar', 'target\document-intelligence-0.1.0.jar' -WorkingDirectory '%JAVA_DIR%' -WindowStyle Hidden"
) else (
    powershell -NoProfile -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'mvn.cmd spring-boot:run' -WorkingDirectory '%JAVA_DIR%' -WindowStyle Hidden"
)

:wait_services
:: 3. Ожидание готовности backend-сервисов
echo.
echo Ожидание готовности backend-сервисов...
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
    echo [OK] Все сервисы запущены и готовы к работе!
) else (
    echo [!] Серверы еще инициализируются, запускаем интерфейс...
)

:: 4. Запуск Electron UI
echo [3/3] Открытие интерфейса Electron...
cd /d "%ELECTRON_DIR%"
set ELECTRON_RUN_AS_NODE=
call npm start

:: Завершение фоновых сервисов, если больше нет активных окон Electron
powershell -NoProfile -Command "if (Get-Process electron -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Остановка фоновых сервисов...
    call "%ROOT_DIR%stop.bat"
)
exit /b 0
