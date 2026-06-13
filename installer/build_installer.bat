@echo off
REM ============================================================================
REM  build_installer.bat — one-shot build of RockySetup.exe (Phase 1).
REM  Chain: PyInstaller (both exes) -> stage sidecar -> compile Inno Setup.
REM  Run from the repo root:  installer\build_installer.bat
REM ============================================================================

setlocal
set REPO=%~dp0..
cd /d "%REPO%"

echo.
echo === [1/4] Building mcp_server.exe ===
pyinstaller mcp_server.spec --noconfirm
if errorlevel 1 goto fail

echo.
echo === [2/4] Building rocky.exe (onedir) ===
pyinstaller rocky.spec --noconfirm
if errorlevel 1 goto fail

echo.
echo === [3/4] Staging mcp_server.exe + purging sprites (license) ===
copy /Y dist\mcp_server.exe dist\rocky\ >nul
if errorlevel 1 goto fail
REM Hard guarantee no upstream sprite art ends up in the installer. The .iss
REM also Excludes sprites\, but deleting here is deterministic. Rocky
REM re-downloads them on first run (Phase 2).
if exist dist\rocky\sprites rmdir /S /Q dist\rocky\sprites

echo.
echo === [4/4] Compiling installer (Inno Setup) ===
REM Resolve ISCC.exe: PATH first, then default install locations.
where iscc >nul 2>nul
if %errorlevel%==0 (
    iscc installer\rocky.iss
) else if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer\rocky.iss
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    "%ProgramFiles%\Inno Setup 6\ISCC.exe" installer\rocky.iss
) else (
    echo [!] Inno Setup compiler ^(ISCC.exe^) not found.
    echo     Install it:  winget install JRSoftware.InnoSetup
    goto fail
)
if errorlevel 1 goto fail

echo.
echo === DONE ===
echo Installer: installer\Output\RockySetup.exe
goto end

:fail
echo.
echo [!] Build failed. See the output above.
exit /b 1

:end
endlocal
