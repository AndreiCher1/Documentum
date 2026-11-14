# Замер скорости и памяти Documentum на этом компьютере.
# Запуск: сначала откройте Documentum и загрузите хотя бы один документ, затем запустите «Замер.cmd».
# Результат — файл «замер.txt» рядом со скриптом. Его можно отправить разработчику.

param([switch]$Quiet)      # -Quiet: не открывать результат в Блокноте

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8085/api/editor/documents"
$report = Join-Path $PSScriptRoot "замер.txt"
$lines = New-Object System.Collections.Generic.List[string]
function Say($text) { Write-Host $text; $lines.Add($text) }

function Post-Json($url, $obj, $timeoutSec) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($obj | ConvertTo-Json -Compress))
    $resp = Invoke-WebRequest $url -Method Post -Body $bytes -ContentType "application/json; charset=utf-8" -UseBasicParsing -TimeoutSec $timeoutSec
    $parsed = [Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) | ConvertFrom-Json
    return $parsed
}
function Get-Json($url) {
    # через переменную: в PowerShell 5.1 ConvertFrom-Json отдаёт JSON-массив одним объектом, а так он раскрывается в элементы
    $resp = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 30
    $parsed = [Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) | ConvertFrom-Json
    return $parsed
}
function Memory-Now() {
    $rows = @()
    foreach ($port in 8000, 8085) {
        $owner = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess
        if ($owner) { $proc = Get-Process -Id $owner; $rows += [pscustomobject]@{ Part = $(if ($port -eq 8000) { "AI-сервис" } else { "Сервер данных" }); MB = [int]($proc.WorkingSet64 / 1MB) } }
    }
    $ui = (Get-Process -Name "Documentum-UI" -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum
    $rows += [pscustomobject]@{ Part = "Интерфейс"; MB = [int]($ui / 1MB) }
    return $rows
}
function Say-Memory($title) {
    $rows = Memory-Now
    $total = ($rows | Measure-Object MB -Sum).Sum
    $os = Get-CimInstance Win32_OperatingSystem
    Say ("{0}: всего {1} МБ ({2}); свободно памяти в системе {3:N1} ГБ" -f $title, $total, (($rows | ForEach-Object { "$($_.Part) $($_.MB)" }) -join ", "), ($os.FreePhysicalMemory / 1MB))
}

Say ("Замер Documentum, {0:dd.MM.yyyy HH:mm}" -f (Get-Date))
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$os = Get-CimInstance Win32_OperatingSystem
Say ("Процессор: {0} (ядер {1}, потоков {2})" -f $cpu.Name.Trim(), $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors)
Say ("Память: {0:N1} ГБ, свободно {1:N1} ГБ. Система: {2}" -f ($os.TotalVisibleMemorySize / 1MB), ($os.FreePhysicalMemory / 1MB), $os.Caption)

try { $docs = @(Get-Json $base) } catch {
    Say "Documentum не отвечает. Запустите программу, дождитесь надписи «ИИ готов» и повторите замер."
    $lines | Set-Content $report -Encoding utf8; return
}
$status = Get-Json "$base/assistant/status"
Say ("Профиль: {0}. Языковая модель: {1}{2}" -f $status.profile, $status.model, $(if ($status.available) { "" } else { " — НЕ подключена: $($status.reason)" }))
$search = $status.search
Say ("Поиск по смыслу: {0}" -f $(if ($search.available) { "модель $($search.model), готово абзацев $($search.ready) из $($search.blocks)" } else { "выключен — $($search.reason)" }))
Say ("Документов в базе: {0}" -f $docs.Count)
Say-Memory "Память до вопросов"

if (-not $docs.Count) {
    Say "В базе нет документов: загрузите договор (DOCX или PDF) и повторите замер — без него вопросы задать не о чем."
    $lines | Set-Content $report -Encoding utf8; if (-not $Quiet) { Start-Process notepad $report }; return
}
$doc = $docs | Sort-Object { $_.fileSize } -Descending | Select-Object -First 1
Say ("Документ для замера: «{0}» ({1:N0} КБ), номер {2}" -f $doc.title, ($doc.fileSize / 1KB), $doc.id)

function Time-It($title, [scriptblock]$action) {
    Write-Host "… $title"
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try { $result = & $action; $note = "" } catch { $result = $null; $note = " — ОШИБКА: $($_.Exception.Message)" }
    $watch.Stop()
    Say ("{0}: {1:N1} с{2}" -f $title, $watch.Elapsed.TotalSeconds, $note)
    return $result
}

Time-It "Проверка по правилам и сверка с базой" { Post-Json "$base/$($doc.id)/check" @{ html = $null; deep = $false } 300 } | Out-Null
$first = Time-It "Вопрос по документу, первый (с загрузкой модели)" { Post-Json "$base/assistant" @{ question = "О чём этот документ и кто его стороны?"; context = $null; docId = $doc.id } 900 }
if ($first) { Say ("   ответ модели: {0}; текст: {1}" -f $(if ($first.generated) { "да" } else { "нет (шаблон)" }), $first.summary) }
$second = Time-It "Вопрос по документу, второй (модель уже в памяти)" { Post-Json "$base/assistant" @{ question = "Какие сроки и суммы указаны в документе?"; context = $null; docId = $doc.id } 900 }
if ($second) { Say ("   ответ модели: {0}; текст: {1}" -f $(if ($second.generated) { "да" } else { "нет (шаблон)" }), $second.summary) }
Time-It "Вопрос по всей базе («Все документы»)" { Post-Json "$base/assistant" @{ question = "Все документы"; context = $null } 900 } | Out-Null
$found = Time-It "Поиск по смыслу («срок оплаты и ответственность»)" { Get-Json "$base/search?q=$([uri]::EscapeDataString('срок оплаты и ответственность'))&mode=sem" }
Say-Memory "Память после вопросов (модели загружены)"
$deep = Time-It "Смысловая проверка моделью (самое долгое)" { Post-Json "$base/$($doc.id)/check" @{ html = $null; deep = $true } 1800 }
if ($deep -and $deep.semantic) { Say ("   прочитано частей: {0} из {1}, находок модели: {2}" -f $deep.semantic.chunks, $deep.semantic.total, $deep.semantic.found) }
Say-Memory "Память в конце"
$status = Get-Json "$base/assistant/status"
Say ("Поиск по смыслу в конце: готово абзацев {0} из {1}" -f $status.search.ready, $status.search.blocks)

$lines | Set-Content $report -Encoding utf8
Say "Готово. Результат записан в $report"
if (-not $Quiet) { Start-Process notepad $report }
