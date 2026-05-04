# How to Run Rocky

Two routes: **prebuilt `rocky.exe`** (no Python needed beyond Claude CLI) or
**from source** (Python + PyQt6).

Either way you need:

- Windows 10 or 11
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code)
  installed and authenticated once: `npm install -g @anthropic-ai/claude-code`
  then `claude login`
- The 6 sprite PNGs from the upstream
  [itmesneha/agentrocky](https://github.com/itmesneha/agentrocky)
  `Assets.xcassets` (not redistributed in this repo)

## Route A — Prebuilt `rocky.exe`

### 1. Get the build folder

Either grab a release zip, or build it yourself (see *Building* below). Either
way you should end up with a folder like:

```
rocky\
  rocky.exe
  mcp_server.exe
  _internal\           Qt + Python runtime — do not delete or rename
  sounds\              bundled voice clips
```

Keep all four entries together. `_internal\` holds `python314.dll`, the Qt
DLLs, and every other dependency. Moving `rocky.exe` out of this folder
breaks it (you'll get *"Failed to load Python DLL"*).

### 2. Drop the sprites in

Create `rocky\sprites\` next to `rocky.exe` and copy the 6 PNGs from the
upstream repo into it:

```
rocky\sprites\stand.png
rocky\sprites\walkleft1.png
rocky\sprites\walkleft2.png
rocky\sprites\jazz1.png
rocky\sprites\jazz2.png
rocky\sprites\jazz3.png
```

Filenames are exact. Missing any → startup error dialog with a button to open
the sprites folder.

### 3. Run

Double-click `rocky.exe`. Sprite walks above the taskbar. Click him to open
chat. **Ctrl+Alt+R** anywhere summons chat. Tray icon for menu.

First launch will trigger Windows SmartScreen (*"unrecognized app"*) because
the binary is unsigned. Click **More info → Run anyway**.

### 4. Where state lives

- `~\.agentrocky\` — `audit.log`, `reminders.json`, `health.json`,
  `mcp_config.json`, `log.txt` (crash log)
- `~\agentrocky-workspace\` — Claude's sandbox cwd. Override with
  `AGENTROCKY_CWD` env var.

## Route B — From source

```powershell
git clone <this-repo-url>
cd agentrocky_windows

pip install -r requirements.txt

npm install -g @anthropic-ai/claude-code
claude login
```

Drop the 6 sprite PNGs into `.\sprites\` (same filenames as above).

Run:

```powershell
pythonw rocky.py        # no console window
python   rocky.py       # with console — debugging
```

Tested on Python 3.10 – 3.14, PyQt6 6.11.

## Building the exe yourself

```powershell
pyinstaller mcp_server.spec --noconfirm
pyinstaller rocky.spec --noconfirm
```

Output:

```
dist\
  mcp_server.exe        onefile sidecar (~21 MB)
  rocky\
    rocky.exe           launcher (~3 MB)
    _internal\          Qt + Python runtime (~99 MB)
```

Ship `dist\rocky\` as one folder. To package for end users:

1. Copy `dist\mcp_server.exe` → `dist\rocky\mcp_server.exe` (sibling of
   `rocky.exe`).
2. Copy or have the user drop `sprites\` next to `rocky.exe`.
3. Zip `dist\rocky\` and distribute.

Don't ship `dist\rocky.exe` (the empty stub) or anything from `build\` —
that's a PyInstaller scratch folder; its `rocky.exe` has no `_internal\` and
will fail with *"Failed to load Python DLL"*.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| *"Failed to load Python DLL `_internal\python314.dll`"* | Running `build\rocky\rocky.exe` instead of `dist\rocky\rocky.exe`, or `rocky.exe` was moved out of its folder | Run from `dist\rocky\`, keep `_internal\` next to it |
| *"Missing sprite files in ./sprites/"* | Sprites not staged | Copy 6 PNGs into `sprites\` next to `rocky.exe` (or next to `rocky.py` for source runs) |
| Sprite shows but chat says *"claude executable not found"* | Claude CLI not on PATH | `npm install -g @anthropic-ai/claude-code`, then `claude login` |
| Reminders / `rocky.note` etc. don't work | `mcp_server.exe` not next to `rocky.exe`, or stale `mcp_config.json` from a source run | Ensure sibling layout, delete `~\.agentrocky\mcp_config.json`, relaunch |
| Crash with no dialog | Look at `~\.agentrocky\log.txt` | Excepthook writes a traceback there for any unhandled exception |
| Two `rocky.exe` processes in Task Manager | Normal — PyInstaller bootloader stub + main app | Don't kill them individually; use tray → Quit |

## Safety reminder

Rocky runs `claude --dangerously-skip-permissions`. Claude executes tools
without per-call confirmation. Mitigations: workspace sandbox, one-time
per-session confirmation, audit log, `rocky.open` workspace-only,
`rocky.launch_app` whitelist-only. Don't run if you're not OK with that.
