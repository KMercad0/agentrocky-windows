@echo off
REM agentrocky-windows first-run setup helper.
REM Walks the user through: Node check, claude CLI install, login, sprite drop.

setlocal
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo ============================================
echo  agentrocky-windows  first-run setup
echo ============================================
echo.

REM --- step 1: Node.js -------------------------------------------------------
where node >nul 2>nul
if errorlevel 1 (
    echo [!] Node.js not found.
    echo     Install it from https://nodejs.org/  (LTS is fine^), then run setup.bat again.
    start "" "https://nodejs.org/"
    pause
    exit /b 1
)
echo [ok] Node.js found.

REM --- step 2: Claude Code CLI ----------------------------------------------
where claude >nul 2>nul
if errorlevel 1 (
    echo.
    echo [..] Installing Claude Code CLI globally  (npm i -g @anthropic-ai/claude-code^)...
    call npm install -g @anthropic-ai/claude-code
    if errorlevel 1 (
        echo [!] npm install failed. Try running this script as Administrator.
        pause
        exit /b 1
    )
) else (
    echo [ok] Claude CLI already installed.
)

REM --- step 3: claude login --------------------------------------------------
echo.
echo [..] Launching 'claude login' — sign in to your Anthropic account in the browser.
echo     Close that window when done; setup will continue.
echo.
call claude login

REM --- step 4: sprites -------------------------------------------------------
if not exist "%SCRIPT_DIR%sprites" mkdir "%SCRIPT_DIR%sprites"
set NEED_SPRITES=0
for %%F in (stand.png walkleft1.png walkleft2.png jazz1.png jazz2.png jazz3.png) do (
    if not exist "%SCRIPT_DIR%sprites\%%F" set NEED_SPRITES=1
)

if %NEED_SPRITES%==1 (
    echo.
    echo [!] Sprite PNGs missing. They're not bundled here  (original author's art^).
    echo     1. Opening the upstream repo  (download the 6 PNGs from Assets.xcassets^)
    echo     2. Opening your local sprites folder  (drop the 6 files in there^)
    echo.
    echo     Required filenames:
    echo       stand.png  walkleft1.png  walkleft2.png
    echo       jazz1.png  jazz2.png      jazz3.png
    echo.
    start "" "https://github.com/itmesneha/agentrocky"
    start "" "%SCRIPT_DIR%sprites"
    echo Drop the 6 files, then press any key to continue...
    pause >nul
)

REM --- step 5: launch --------------------------------------------------------
echo.
echo [ok] Setup done. Launching rocky.exe...
start "" "%SCRIPT_DIR%rocky.exe"

endlocal
