; Установщик Documentum (Inno Setup 6).
; Сначала собрать папку поставки:  powershell -ExecutionPolicy Bypass -File packaging\build-dist.ps1
; Затем:                            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\Documentum.iss
; Результат:                        dist\Documentum-Setup.exe (и части .bin рядом, если размер больше 2 ГБ)
;
; Программа ставится в профиль пользователя — права администратора не нужны.
; Так сделано намеренно: база документов и журналы лежат в папке программы, она должна быть доступна на запись.

#define AppName "Documentum"
#define AppVersion "0.2.0"

[Setup]
AppId={{8C6E0D5A-6C1B-4E0B-9B1F-0D0C5A7E2F41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Documentum
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Documentum-Setup
Compression=lzma2/fast
SolidCompression=no
; модели занимают несколько гигабайт — установщик делится на части по 2 ГБ
DiskSpanning=yes
DiskSliceSize=2000000000
WizardStyle=modern
UninstallDisplayIcon={app}\Documentum.exe
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\Documentum\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Documentum.exe"; WorkingDir: "{app}"
Name: "{group}\Инструкция"; Filename: "{app}\Инструкция.md"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\Documentum.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Documentum.exe"; Description: "Запустить Documentum"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; журналы и служебные файлы; базу документов (java-backend\data, uploads) и поисковый индекс удаление НЕ трогает
Type: files; Name: "{app}\launcher.log"
Type: files; Name: "{app}\document-intelligence\ai-service\ai.log"
Type: files; Name: "{app}\document-intelligence\java-backend\backend.log"
Type: filesandordirs; Name: "{app}\runtime\python\Lib\__pycache__"
