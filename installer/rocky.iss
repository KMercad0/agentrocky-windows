; Inno Setup script for agentrocky-windows — Phase 1 of the 1-stop install.
; Bundles the existing PyInstaller onedir build (dist\rocky\) into one
; per-user RockySetup.exe. No admin/UAC prompt. No Python required by the user.
;
; Build:  iscc installer\rocky.iss      (run from the repo root)
;         output lands in installer\Output\RockySetup.exe
;
; Prereqs before compiling:
;   1. pyinstaller mcp_server.spec --noconfirm
;   2. pyinstaller rocky.spec      --noconfirm
;   3. copy dist\mcp_server.exe dist\rocky\        (sidecar must sit next to rocky.exe)
;   4. Install Inno Setup 6:  winget install JRSoftware.InnoSetup
;
; Sprites are intentionally NOT bundled (upstream art, license — see
; one_stop_install_plan.md). Rocky fetches them on first run (Phase 2).

#define AppName        "Rocky"
#define AppVersion     "1.0.0"
#define AppPublisher   "agentrocky-windows (community port)"
#define AppExeName     "rocky.exe"
#define AppURL         "https://github.com/KMercad0/agentrocky-windows"

[Setup]
; A fixed AppId keeps upgrades/uninstall consistent across versions. Do not change.
AppId={{A7E3F1C2-9B4D-4E6A-8F2C-1D5B7A0E9C34}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install → no admin prompt, lands in %LOCALAPPDATA%\Rocky.
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=RockySetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Uninstaller uses the app exe's icon.
UninstallDisplayIcon={app}\{#AppExeName}
; SetupIconFile=rocky.ico   ; uncomment once an .ico is added to installer\

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startupicon"; Description: "Start Rocky automatically when I log in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; The whole onedir payload (rocky.exe + _internal\ + mcp_server.exe + setup.bat),
; recursively, EXCEPT the dev's local sprites\ folder (not redistributable).
Source: "..\dist\rocky\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "sprites\*,setup.bat"

[Icons]
Name: "{group}\{#AppName}";              Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
; Startup shortcut (per-user) — fires the "start at login" task.
Name: "{userstartup}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
; Offer to launch Rocky at the end of setup. First launch triggers the
; sprite download (Phase 2) and backend wizard (Phase 3).
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove sprites that Rocky downloaded into the install dir at runtime, so an
; uninstall leaves nothing behind. (User data under %USERPROFILE%\.agentrocky\
; and the workspace are left intact on purpose — documented in How-to-Run.)
Type: filesandordirs; Name: "{app}\sprites"
