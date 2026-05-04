# How to Run Rocky

Three routes, easiest first:

1. **Release zip + `setup.bat`** — recommended for most people. No Python.
2. **Build the exe yourself** — if you don't trust prebuilt binaries.
3. **Run from source** — Python + PyQt6, for developers / contributors.

You need (all routes):

- Windows 10 or 11
- An Anthropic account (for `claude login`)
- Node.js LTS — only if you don't already have it. `setup.bat` will tell you.
- The 6 sprite PNGs from the upstream
  [itmesneha/agentrocky](https://github.com/itmesneha/agentrocky) repo. Not
  redistributed here out of respect for the original author. `setup.bat`
  walks you through fetching them.

---

## Route 1 — Release zip (recommended)

### 1. Download

Grab `agentrocky-windows-vX.Y.Z.zip` from the
[Releases](https://github.com/KMercad0/agentrocky-windows/releases) page.

### 2. Unzip

Anywhere is fine — Desktop, Documents, wherever. You'll get a folder with:

```
rocky.exe          launcher
mcp_server.exe     MCP sidecar (must stay next to rocky.exe)
setup.bat          first-run helper
_internal\         Qt + Python runtime — never delete or move
```

Keep the four entries together. `_internal\` holds `python314.dll` and Qt
DLLs. Moving `rocky.exe` out of this folder breaks it (*"Failed to load
Python DLL"* error).

### 3. Double-click `setup.bat`

It will:

- check Node.js is installed (opens nodejs.org if not)
- install the Claude Code CLI globally (`npm i -g @anthropic-ai/claude-code`)
- run `claude login` — sign in to your Anthropic account in the browser
- open the upstream sprite repo + your local `sprites\` folder so you can
  drop the 6 PNGs in:
  `stand.png`, `walkleft1.png`, `walkleft2.png`,
  `jazz1.png`, `jazz2.png`, `jazz3.png`
- launch `rocky.exe`

That's the whole install. After this first run, just double-click `rocky.exe`
to start him next time.

### Windows SmartScreen warning

First launch shows *"Windows protected your PC"*. Click **More info → Run
anyway**. The exe is unsigned (code signing roadmap).

---

## Route 2 — Build the exe yourself

Requires Python 3.10–3.14 and the source repo cloned.

```powershell
git clone https://github.com/KMercad0/agentrocky-windows
cd agentrocky-windows
pip install -r requirements.txt pyinstaller

pyinstaller mcp_server.spec --noconfirm
pyinstaller rocky.spec --noconfirm
```

Stage the runtime layout:

```powershell
copy dist\mcp_server.exe dist\rocky\
copy setup.bat           dist\rocky\
```

Then go to `dist\rocky\` and follow Route 1 step 3 (double-click setup.bat).

Don't run `build\rocky\rocky.exe` — that's a PyInstaller scratch folder
without `_internal\`.

---

## Route 3 — From source

For developers / contributors. No exe.

```powershell
git clone https://github.com/KMercad0/agentrocky-windows
cd agentrocky-windows

pip install -r requirements.txt
npm install -g @anthropic-ai/claude-code
claude login
```

Drop the 6 sprite PNGs into `.\sprites\` (same filenames as Route 1).

Run:

```powershell
pythonw rocky.py        # no console window
python   rocky.py       # with console — debugging
```

Tested on Python 3.10–3.14, PyQt6 6.11.

---

## Where state lives

- `~\.agentrocky\` — `audit.log`, `reminders.json`, `health.json`,
  `mcp_config.json`, `log.txt` (crash log)
- `~\agentrocky-workspace\` — Claude's sandbox cwd. Override with
  `AGENTROCKY_CWD` env var.

## Uninstall

Delete the `rocky\` folder. Optional cleanup:

- `%USERPROFILE%\.agentrocky\` — reminders, audit log, mcp config
- `%USERPROFILE%\agentrocky-workspace\` — Claude's sandbox cwd
- `npm uninstall -g @anthropic-ai/claude-code` — if you don't need claude
  CLI for anything else

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| *"Failed to load Python DLL `_internal\python314.dll`"* | Running `build\rocky\rocky.exe` instead of `dist\rocky\rocky.exe`, or `rocky.exe` was moved out of its folder | Run from the unzipped/dist folder, keep `_internal\` next to it |
| *"Missing sprite files in ./sprites/"* | Sprites not staged | Drop the 6 PNGs into `sprites\` next to `rocky.exe` (or next to `rocky.py` for source runs) |
| Sprite shows but chat says *"claude executable not found"* | Claude CLI not on PATH | Re-run `setup.bat`, or manually: `npm install -g @anthropic-ai/claude-code` then `claude login` |
| Reminders / `rocky.note` etc. don't work | `mcp_server.exe` not next to `rocky.exe`, or stale `mcp_config.json` from a source run | Ensure sibling layout, delete `~\.agentrocky\mcp_config.json`, relaunch |
| Crash with no dialog | Look at `~\.agentrocky\log.txt` | Excepthook writes a traceback there for any unhandled exception |
| Two `rocky.exe` processes in Task Manager | Normal — PyInstaller bootloader stub + main app | Don't kill them individually; use tray → Quit |
| `setup.bat` flashes and closes | Likely npm permission error | Right-click setup.bat → *Run as Administrator* |

## Safety reminder

Rocky runs `claude --dangerously-skip-permissions`. Claude executes tools
without per-call confirmation. Mitigations: workspace sandbox, one-time
per-session confirmation, audit log, `rocky.open` workspace-only,
`rocky.launch_app` whitelist-only. Don't run if you're not OK with that.
