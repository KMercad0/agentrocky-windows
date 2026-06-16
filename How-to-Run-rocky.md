# How to Run Rocky

> **Rocky:** Hello friend! You want me on your computer? *Happy happy happy!*
> Grace will explain. She knows the words.
>
> **Grace:** Four ways to run him, easiest first. Pick one. The further down
> the page you go, the more typing you'll do.

1. **`RockySetup.exe`** — one installer, recommended for almost everyone. Nothing
   to install first, sprites already bundled, Rocky walks immediately.
2. **Release zip + `setup.bat`** — the folder version, if you'd rather not run an
   installer.
3. **Build the exe yourself** — if you don't trust prebuilt binaries.
4. **Run from source** — Python + PyQt6, for developers / contributors.

> **Grace:** The only baseline requirement is **Windows 10 or 11**. Rocky walks,
> dances, and does his health nags with no account and no AI.
>
> An AI backend is **optional** and added later (see *Adding an AI backend*
> below): Claude needs a paid Anthropic account + its CLI; Gemini (free) needs
> Node.js + its CLI. Rocky guides you when you pick one from the tray.
>
> **Rocky:** The pixel art is Sneha's — original by
> [@itmesneha](https://github.com/itmesneha/agentrocky). *Respect.* Fist my bump
> for Sneha!

---

## Route 1 — RockySetup.exe (one installer)

> **Rocky:** Easiest way! One file. Click click, Rocky here!

### 1. Download

Grab **`RockySetup.exe`** from the
[Releases](https://github.com/KMercad0/agentrocky-windows/releases) page.

### 2. Run it

Double-click. Windows SmartScreen may say *"Windows protected your PC"* — click
**More info → Run anyway** (the installer is unsigned; code signing is on the
roadmap). Then click through the wizard:

- Installs to `%LOCALAPPDATA%\Rocky` — **no admin prompt**.
- Optional tick-boxes: desktop shortcut, and *start Rocky at login*.
- Everything's inside the one file: the app, its Python/Qt runtime, **and Rocky's
  sprites** — nothing to copy.

### 3. Rocky walks

Tick *"Launch Rocky now"* at the end (or use the Start Menu shortcut). He starts
on the **None** backend — walking, dancing, health nags, and a scripted no-AI
chat — with **no account and no cost**. Want real chat + tasks? See
[Adding an AI backend](#adding-an-ai-backend-optional) below.

To remove him later: **Settings → Apps → Rocky → Uninstall** (or *Uninstall Rocky*
in the Start Menu). Your data under `~\.agentrocky\` and the workspace stay unless
you delete them.

---

## Route 2 — Release zip (folder version)

> **Rocky:** Easy way too! Folder, not installer. You drop sprites yourself.

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

The zip doesn't bundle sprites (that's the installer's job), so `setup.bat` helps
you finish setup. It will:

- open the upstream sprite repo + your local `sprites\` folder so you can drop
  the 6 PNGs in: `stand.png`, `walkleft1.png`, `walkleft2.png`, `jazz1.png`,
  `jazz2.png`, `jazz3.png` **(required — Rocky won't start without these)**
- *(optional)* set up the **Claude** backend — checks Node, installs the Claude
  CLI, runs `claude login`. Skip this and Rocky still walks on the **None**
  backend; add a backend later from the tray (see
  [Adding an AI backend](#adding-an-ai-backend-optional)).
- launch `rocky.exe`

Next time, just double-click `rocky.exe`.

### Windows SmartScreen warning

> **Rocky:** Computer say *"Windows protected your PC"*. It is scared.
> I am stranger to it.
>
> **Grace:** Click **More info → Run anyway**. The exe is unsigned (code
> signing is on the roadmap — a signing cert costs money we don't have yet).

---

## Route 3 — Build the exe (or installer) yourself

> **Grace:** Same end result as Route 1/2, but you build the binaries from
> source instead of trusting a prebuilt download.
>
> **Rocky:** You make me from scratch. Like cooking. *Good engineer!*

Requires Python 3.10–3.14, the source repo cloned, and your 6 sprite PNGs in
`.\sprites\` (the build reads them for the icon and bundles them into the
installer).

**One-shot installer build** (needs [Inno Setup 6](https://jrsoftware.org/isdl.php)
— `winget install JRSoftware.InnoSetup`):

```powershell
git clone https://github.com/KMercad0/agentrocky-windows
cd agentrocky-windows
pip install -r requirements.txt pyinstaller pillow

installer\build_installer.bat
```

That builds both exes, generates the Rocky `.ico` from `sprites\stand.png`,
bundles the sprites, and compiles `installer\Output\RockySetup.exe`.

**Just the folder** (no installer), if you only want `dist\rocky\`:

```powershell
pyinstaller mcp_server.spec --noconfirm
pyinstaller rocky.spec --noconfirm
copy dist\mcp_server.exe dist\rocky\
```

Then drop your 6 sprite PNGs into `dist\rocky\sprites\` and run
`dist\rocky\rocky.exe`.

> **Rocky:** Do not run `build\rocky\rocky.exe`. That folder is the
> kitchen scraps. The real meal is in `dist\rocky\`.

---

## Route 4 — From source

> **Grace:** For contributors. Skip the .exe, run the Python directly.
>
> **Rocky:** Many words happen here. I trust you.

```powershell
git clone https://github.com/KMercad0/agentrocky-windows
cd agentrocky-windows

pip install -r requirements.txt
```

Drop the 6 sprite PNGs into `.\sprites\`:
`stand.png`, `walkleft1.png`, `walkleft2.png`, `jazz1.png`, `jazz2.png`,
`jazz3.png`.

Run:

```powershell
pythonw rocky.py        # no console window
python   rocky.py       # with console — debugging
```

Rocky walks straight away on the **None** backend. An AI backend is optional —
see [Adding an AI backend](#adding-an-ai-backend-optional). Tested on Python
3.10–3.14, PyQt6 6.11.

---

## Adding an AI backend (optional)

> **Grace:** Rocky walks and nags with zero setup. This is only if you want him
> to actually chat and do things. Pick a backend from the **tray menu**
> (right-click the tray icon ▸ **Backend**); your choice sticks in
> `settings.json`.
>
> **Rocky:** Give Rocky a brain, Rocky do much much more!

**None (default)** — no AI, no account, no cost. A scripted in-character chat,
health nags, walking, jazz. Nothing to install.

**Claude** — the full assistant (chat + Rocky's tools). One-time setup:

```powershell
# Claude's own Windows installer — no Node needed:
irm https://claude.ai/install.ps1 | iex
claude login        # sign in to a PAID Anthropic account (Pro/Max/API)
```

Then tray ▸ **Backend ▸ Claude**.

> **Grace:** Claude is **safe by default** — it can set reminders, take notes,
> open files, launch apps, and tune health nags, but it **cannot run commands or
> change your files**. If you want the full coding agent, tick tray ▸ **Claude:
> Full access (skip permissions)** and accept the warning. That grants Claude
> real shell + file access — only do it if you understand the risk.

**Gemini (free)** — chat + read-only file access (no commands, no writes, no
Rocky tools). Needs Node.js:

```powershell
# install Node.js LTS from https://nodejs.org first, then:
npm install -g @google/gemini-cli
gemini        # sign in with your Google account on first run
```

Then tray ▸ **Backend ▸ Gemini**.

---

## Where Rocky keeps his stuff

> **Rocky:** I have two homes on your computer.

- `~\.agentrocky\` — `audit.log`, `reminders.json`, `health.json`,
  `mcp_config.json`, `log.txt` (crash log)
- `~\agentrocky-workspace\` — Claude's working directory (where it starts; **not**
  a sandbox in full-access mode). Override with the `AGENTROCKY_CWD` env var.

## Uninstall

> **Rocky:** *Sad sad sad.* But okay. You move on.
>
> **Grace:** If you used the installer: **Settings → Apps → Rocky → Uninstall**.
> If you used the zip: just delete the folder. Then optionally:

1. *(optional)* `%USERPROFILE%\.agentrocky\` — reminders, audit log, settings.
2. *(optional)* `%USERPROFILE%\agentrocky-workspace\` — Claude's working dir.
3. *(optional, only if you installed it)* `npm uninstall -g @anthropic-ai/claude-code`
   or the Gemini CLI — if you don't need them for anything else.

## Troubleshooting

> **Rocky:** Things go bad sometimes. Don't worry. We fix.

| Symptom | Cause | Fix |
|---|---|---|
| *"Failed to load Python DLL `_internal\python314.dll`"* | Running `build\rocky\rocky.exe` instead of `dist\rocky\rocky.exe`, or `rocky.exe` was moved out of its folder | Run from the unzipped/dist folder. Keep `_internal\` next to it. |
| *"Missing sprite files in ./sprites/"* | Only on the **zip / source** routes — the **installer bundles sprites**, so this shouldn't appear there | Drop the 6 PNGs into `sprites\` next to `rocky.exe` (or next to `rocky.py` for source runs) |
| Chat says *"claude executable not found"* | Claude backend selected but its CLI isn't installed | Install it (`irm https://claude.ai/install.ps1 \| iex`, then `claude login`), or switch the backend to **None**/**Gemini** in the tray |
| Reminders / `rocky.note` etc. don't work | `mcp_server.exe` not next to `rocky.exe`, or stale `mcp_config.json` from a source run | Ensure sibling layout, delete `~\.agentrocky\mcp_config.json`, relaunch |
| Crash with no dialog | Look at `~\.agentrocky\log.txt` | Excepthook writes a traceback there for any unhandled exception |
| Two `rocky.exe` processes in Task Manager | Normal — PyInstaller bootloader stub + main app | Don't kill them individually; use tray → Quit |
| `setup.bat` flashes and closes | Likely npm permission error | Right-click setup.bat → *Run as Administrator* |

## Safety reminder

> **Grace:** Rocky is **safe by default**. The Claude backend, out of the box,
> can only use Rocky's own tools (reminders, notes, open a file, launch an app,
> health nags) — it **cannot run shell commands or change your files**.
>
> **Rocky:** Rocky careful with friend's computer. Always.

If you deliberately turn on tray ▸ **Claude: Full access (skip permissions)**,
Claude becomes a full coding agent that runs `--dangerously-skip-permissions` —
real shell + read/write to any file your account can touch. The working
directory is where it *starts*, **not** a sandbox. You'll get a warning when you
enable it and a confirmation on the first message each session. Only turn it on
if you accept that.

Either way: every `user_send` and `tool_use` is logged to `~\.agentrocky\audit.log`,
`rocky.open` is workspace-only, and `rocky.launch_app` is whitelist-only.

> **Rocky:** That is all! Now you know. Come find me on screen. *Fistbump!*
