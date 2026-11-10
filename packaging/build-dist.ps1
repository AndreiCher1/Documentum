# Сборка поставки Documentum: папка, которую можно скопировать на компьютер без Java, Python и интернета.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build-dist.ps1            # с языковыми моделями (около 5 ГБ)
#   powershell -ExecutionPolicy Bypass -File packaging\build-dist.ps1 -NoModels  # без моделей (около 1,7 ГБ)
#
# Что попадает в dist\Documentum:
#   Documentum.exe                 лаунчер (собирается из DocumentumLauncher.cs)
#   runtime\python                 Python с библиотеками AI-сервиса
#   runtime\jre                    урезанная Java для сервера данных (jlink)
#   runtime\paddlex                модели распознавания сканов
#   document-intelligence\...      интерфейс, сервер данных (jar), AI-сервис, модели
#   Инструкция.md
#
# Перед сборкой: mvn -o -q package -DskipTests (java-backend) и npm run build:portable (electron-app).
# Установщик из готовой папки делает packaging\Documentum.iss (нужен Inno Setup 6).

param(
    [switch]$NoModels,
    [string]$PythonHome = "",
    [string]$JdkHome = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$di = Join-Path $repo "document-intelligence"
$dist = Join-Path $repo "dist\Documentum"
$started = Get-Date

function Step($text) { Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $text) }

function Copy-Tree($from, $to, [string[]]$excludeDirs = @(), [string[]]$excludeFiles = @()) {
    # robocopy: 0–7 — успех, 8 и выше — ошибка
    $cmdArgs = @($from, $to, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/R:1", "/W:1")
    if ($excludeDirs.Count) { $cmdArgs += "/XD"; $cmdArgs += $excludeDirs }
    if ($excludeFiles.Count) { $cmdArgs += "/XF"; $cmdArgs += $excludeFiles }
    & robocopy @cmdArgs | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Не удалось скопировать $from (robocopy $LASTEXITCODE)" }
    $global:LASTEXITCODE = 0
}

function First-ByName($dir) {
    # Программа берёт первый по алфавиту файл .gguf, сравнивая имена побуквенно (как Python). Sort-Object сортирует
    # по правилам языка и ставит «Qwen3.5» раньше «Qwen3-4B» — поэтому сравниваем так же, как программа.
    $files = @(Get-ChildItem $dir -Filter "*.gguf" -File -ErrorAction SilentlyContinue)
    if (-not $files.Count) { return $null }
    $names = [string[]]($files | ForEach-Object Name)
    [Array]::Sort($names, [StringComparer]::Ordinal)
    return $files | Where-Object { $_.Name -ceq $names[0] } | Select-Object -First 1
}

# --- откуда брать Python и JDK
if (-not $PythonHome) {
    $cfg = Get-Content (Join-Path $di "ai-service\venv\pyvenv.cfg") | Where-Object { $_ -match '^home\s*=' }
    $PythonHome = ($cfg -replace '^home\s*=\s*', '').Trim()
}
if (-not (Test-Path (Join-Path $PythonHome "python.exe"))) { throw "Не найден Python: $PythonHome (укажите -PythonHome)" }
if (-not $JdkHome) {
    $jdk = Get-ChildItem "C:\Program Files\Microsoft", "C:\Program Files\Eclipse Adoptium", "C:\Program Files\Java" -Directory -Filter "jdk-21*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($jdk) { $JdkHome = $jdk.FullName }
}
if (-not (Test-Path (Join-Path $JdkHome "bin\jlink.exe"))) { throw "Не найден JDK 21 с jlink (укажите -JdkHome)" }
$jar = Join-Path $di "java-backend\target\document-intelligence-0.1.0.jar"
if (-not (Test-Path $jar)) { throw "Нет $jar — сначала соберите сервер данных: mvn -o -q package -DskipTests" }
$ui = Join-Path $di "portable-ui"
if (-not (Test-Path (Join-Path $ui "Documentum-UI.exe"))) { throw "Нет portable-ui — сначала соберите интерфейс: npm run build:portable" }

Step "Очищаю $dist"
if (Test-Path $dist) {
    # Пустую папку может держать открытое окно проводника или консоль — это не мешает; мешают только оставшиеся файлы
    Remove-Item $dist -Recurse -Force -ErrorAction SilentlyContinue
    $left = @(Get-ChildItem $dist -Recurse -File -ErrorAction SilentlyContinue)
    if ($left.Count) { throw "Не удалось очистить $dist — закройте программы, которые открыли файлы из этой папки (например, $($left[0].FullName))" }
}
New-Item -ItemType Directory -Force $dist | Out-Null

Step "Собираю лаунчер"
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:winexe /optimize+ "/out:$dist\Documentum.exe" /r:System.Windows.Forms.dll /r:System.Drawing.dll (Join-Path $repo "DocumentumLauncher.cs")
if ($LASTEXITCODE -ne 0) { throw "Лаунчер не собрался" }

Step "Копирую интерфейс и сервер данных"
Copy-Tree $ui (Join-Path $dist "document-intelligence\portable-ui")
New-Item -ItemType Directory -Force (Join-Path $dist "document-intelligence\java-backend\target") | Out-Null
Copy-Item $jar (Join-Path $dist "document-intelligence\java-backend\target")

Step "Копирую AI-сервис"
$ai = Join-Path $dist "document-intelligence\ai-service"
Copy-Tree (Join-Path $di "ai-service\app") (Join-Path $ai "app") @("__pycache__")
Copy-Item (Join-Path $di "ai-service\run.py"), (Join-Path $di "ai-service\requirements.txt") $ai
if (-not $NoModels) {
    Step "Копирую языковые модели (это несколько гигабайт)"
    New-Item -ItemType Directory -Force (Join-Path $ai "models\embed") | Out-Null
    # основная модель — первая по алфавиту (её же берёт программа); запасные и недокачанные файлы в поставку не идут
    $llm = First-ByName (Join-Path $di "ai-service\models")
    if ($llm) { Copy-Item $llm.FullName (Join-Path $ai "models") } else { Write-Warning "Языковая модель не найдена — ассистент будет отвечать по шаблону" }
    # лёгкая модель для компьютеров с 8 ГБ памяти: программа сама берёт её, когда памяти меньше 12 ГБ
    $light = First-ByName (Join-Path $di "ai-service\models\light")
    if ($light) {
        New-Item -ItemType Directory -Force (Join-Path $ai "models\light") | Out-Null
        Copy-Item $light.FullName (Join-Path $ai "models\light")
    } else { Write-Warning "Лёгкая модель не найдена — на компьютере с 8 ГБ памяти будет загружаться обычная" }
    $emb = First-ByName (Join-Path $di "ai-service\models\embed")
    if ($emb) { Copy-Item $emb.FullName (Join-Path $ai "models\embed") } else { Write-Warning "Модель поиска по смыслу не найдена — поиск будет по словам" }
}

Step "Копирую Python и библиотеки"
$py = Join-Path $dist "runtime\python"
Copy-Tree $PythonHome $py @("__pycache__", "Doc", "test", "tests", "idlelib", "tkinter", "tcl", "turtledemo", "site-packages", "Scripts") @("*.pyc")
Copy-Tree (Join-Path $di "ai-service\venv\Lib\site-packages") (Join-Path $py "Lib\site-packages") @("__pycache__", "pip", "setuptools", "pytest", "_pytest") @("*.pyc")

Step "Собираю урезанную Java (jlink)"
& (Join-Path $JdkHome "bin\jlink.exe") --add-modules "java.se,jdk.unsupported,jdk.crypto.ec,jdk.zipfs,jdk.management,jdk.charsets,jdk.localedata" `
    --strip-debug --no-man-pages --no-header-files --compress zip-6 --output (Join-Path $dist "runtime\jre")
if ($LASTEXITCODE -ne 0) { throw "jlink завершился с ошибкой" }

$ocr = Join-Path $env:USERPROFILE ".paddlex\official_models"
if (Test-Path $ocr) {
    Step "Копирую модели распознавания сканов"
    Copy-Tree $ocr (Join-Path $dist "runtime\paddlex\official_models")
} else {
    Write-Warning "Модели распознавания сканов не найдены ($ocr): на компьютере без интернета сканы распознаваться не будут"
}

# замер скорости и памяти на компьютере покупателя и запуск в лёгком профиле (как на ПК с 8 ГБ)
Copy-Item (Join-Path $PSScriptRoot "measure.ps1") $dist
Copy-Item (Join-Path $PSScriptRoot "measure.cmd") (Join-Path $dist "Замер.cmd")
Copy-Item (Join-Path $PSScriptRoot "run-light.cmd") (Join-Path $dist "Запуск в лёгком профиле.cmd")

$manual = Join-Path $di "docs\Инструкция.md"
if (Test-Path $manual) { Copy-Item $manual $dist }

Step "Готово"
$parts = @("Documentum.exe", "runtime\python", "runtime\jre", "runtime\paddlex", "document-intelligence\portable-ui",
           "document-intelligence\java-backend", "document-intelligence\ai-service")
foreach ($part in $parts) {
    $path = Join-Path $dist $part
    if (Test-Path $path) {
        $size = (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        if (-not $size) { $size = (Get-Item $path).Length }
        Write-Host ("  {0,-42} {1,8:N0} МБ" -f $part, ($size / 1MB))
    }
}
$total = (Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ("  {0,-42} {1,8:N0} МБ" -f "ВСЕГО", ($total / 1MB))
Write-Host ("Папка поставки: $dist (собрано за {0:N0} с)" -f ((Get-Date) - $started).TotalSeconds)
