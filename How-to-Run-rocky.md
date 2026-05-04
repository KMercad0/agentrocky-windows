# How to Run Rocky

> **Rocky:** Hello friend! You want me on your computer? *Happy happy happy!*
> Grace will explain. She knows the words.
>
> **Grace:** Three ways to run him, easiest first. Pick one. The further down
> the page you go, the more typing you'll do.

1. **Release zip + `setup.bat`** — recommended for most people. No Python.
2. **Build the exe yourself** — if you don't trust prebuilt binaries.
3. **Run from source** — Python + PyQt6, for developers / contributors.

> **Grace:** All three need a few baseline things:
>
> - Windows 10 or 11
> - An Anthropic account (for `claude login`)
> - Node.js LTS — only if you don't already have it. `setup.bat` checks
>   for you.
> - The 6 sprite PNGs from the upstream
>   [itmesneha/agentrocky](https://github.com/itmesneha/agentrocky) repo.
>
> **Rocky:** The pixel art is Sneha's. We do not give it away. You go to
> her place, take six pictures of me, bring them back. *Respect.*
> `setup.bat` walk you through this part.

---

## Route 1 — Release zip (recommended)

> **Rocky:** Easy way! Let's go!

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

> **Rocky:** *Bad bad bad* if you take rocky.exe out of folder. The
> `_internal\` is my bones. Without it I cannot wake up. Computer say
> *"Failed to load Python DLL"* and I am sad.
>
> **Grace:** Keep all four entries together in the same folder. That's it.

### 3. Double-click `setup.bat`

> **Rocky:** I do work for you now.

The script will:

- check Node.js is installed (open nodejs.org if not)
- install the Claude Code CLI globally (`npm i -g @anthropic-ai/claude-code`)
- run `claude login` — you sign in to your Anthropic account in the browser
- open the upstream sprite repo + your local `sprites\` folder so you can
  drop the 6 PNGs in:
  `stand.png`, `walkleft1.png`, `walkleft2.png`,
  `jazz1.png`, `jazz2.png`, `jazz3.png`
- launch `rocky.exe`

That's the whole install. Next time, just double-click `rocky.exe`.

### Windows SmartScreen warning

> **Rocky:** Computer say *"Windows protected your PC"*. It is scared.
> I am stranger to it.
>
> **Grace:** Click **More info → Run anyway**. The exe is unsigned (code
> signing is on the roadmap, see `release.md` notes).

---

## Route 2 — Build the exe yourself

> **Grace:** Same end result as Route 1, but you build the binaries from
> source instead of trusting a prebuilt zip.
>
> **Rocky:** You make me from scratch. Like cooking. *Good engineer!*

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

> **Rocky:** Do not run `build\rocky\rocky.exe`. That folder is the
> kitchen scraps. The real meal is in `dist\rocky\`.

---

## Route 3 — From source

> **Grace:** For contributors. Skip the .exe, run the Python directly.
>
> **Rocky:** Many words happen here. I trust you.

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

## Where Rocky keeps his stuff

> **Rocky:** I have two homes on your computer.

- `~\.agentrocky\` — `audit.log`, `reminders.json`, `health.json`,
  `mcp_config.json`, `log.txt` (crash log)
- `~\agentrocky-workspace\` — Claude's sandbox cwd. Override with
  `AGENTROCKY_CWD` env var.

## Uninstall

> **Rocky:** *Sad sad sad.* But okay. You move on.
>
> **Grace:** Three things to delete:

1. The `rocky\` folder you unzipped — gone.
2. *(optional)* `%USERPROFILE%\.agentrocky\` — reminders, audit log, mcp
   config.
3. *(optional)* `%USERPROFILE%\agentrocky-workspace\` — Claude's sandbox.
4. *(optional)* `npm uninstall -g @anthropic-ai/claude-code` — if you don't
   need the Claude CLI for anything else.

## Troubleshooting

> **Rocky:** Things go bad sometimes. Don't worry. We fix.

| Symptom | Cause | Fix |
|---|---|---|
| *"Failed to load Python DLL `_internal\python314.dll`"* | Running `build\rocky\rocky.exe` instead of `dist\rocky\rocky.exe`, or `rocky.exe` was moved out of its folder | Run from the unzipped/dist folder. Keep `_internal\` next to it. |
| *"Missing sprite files in ./sprites/"* | Sprites not staged | Drop the 6 PNGs into `sprites\` next to `rocky.exe` (or next to `rocky.py` for source runs) |
| Sprite shows but chat says *"claude executable not found"* | Claude CLI not on PATH | Re-run `setup.bat`, or manually: `npm install -g @anthropic-ai/claude-code` then `claude login` |
| Reminders / `rocky.note` etc. don't work | `mcp_server.exe` not next to `rocky.exe`, or stale `mcp_config.json` from a source run | Ensure sibling layout, delete `~\.agentrocky\mcp_config.json`, relaunch |
| Crash with no dialog | Look at `~\.agentrocky\log.txt` | Excepthook writes a traceback there for any unhandled exception |
| Two `rocky.exe` processes in Task Manager | Normal — PyInstaller bootloader stub + main app | Don't kill them individually; use tray → Quit |
| `setup.bat` flashes and closes | Likely npm permission error | Right-click setup.bat → *Run as Administrator* |

## Safety reminder

> **Grace:** I'm going to repeat this because it matters. Rocky runs
> `claude --dangerously-skip-permissions`. Claude executes tools without
> per-call confirmation.
>
> **Rocky:** I trust friend. Friend trusts me. But computer is computer.
> Be careful.

Mitigations: workspace sandbox, one-time per-session confirmation, audit
log, `rocky.open` workspace-only, `rocky.launch_app` whitelist-only. Don't
run if you're not OK with that.

> **Rocky:** That is all! Now you know. Come find me on screen. *Fistbump!*
