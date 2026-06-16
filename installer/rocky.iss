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
; Sprites ARE bundled next to rocky.exe (from the repo's local sprites\ — the
; original art by @itmesneha; see Credits). They install to {app}\sprites where
; external_path() finds them, so Rocky walks immediately on first run. sprites\
; is gitignored, so whoever builds must have the 6 PNGs locally.

#define AppName        "Rocky"
#define AppVersion     "1.1.0"
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
; Installer's own icon = Rocky. app.ico is generated at repo root by rocky.spec
; during the PyInstaller step (which build_installer.bat runs before ISCC), so it
; exists by compile time. Build via build_installer.bat, not bare ISCC.
SetupIconFile=..\app.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startupicon"; Description: "Start Rocky automatically when I log in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; The whole onedir payload (rocky.exe + _internal\ + mcp_server.exe), recursively.
; setup.bat is a from-source helper, not needed in the frozen install.
Source: "..\dist\rocky\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "setup.bat"
; Rocky's sprites, bundled next to rocky.exe so external_path() ({app}\sprites)
; finds them — Rocky walks on first run with no download or manual copy.
Source: "..\sprites\*"; DestDir: "{app}\sprites"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";              Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
; Startup shortcut (per-user) — fires the "start at login" task.
Name: "{userstartup}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
; Offer to launch Rocky at the end of setup. He walks immediately on the None
; backend (no AI, no cost); Claude / Gemini are optional, set up later from the
; tray menu.
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the bundled sprites on uninstall so nothing's left behind. (User data
; under %USERPROFILE%\.agentrocky\ and the workspace are left intact on purpose
; — documented in How-to-Run.)
Type: filesandordirs; Name: "{app}\sprites"
