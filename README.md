# agentrocky-windows

An **unofficial** Windows port of [**agentrocky**](https://github.com/itmesneha/agentrocky)
by [**@itmesneha**](https://github.com/itmesneha) — a desktop pixel-art companion
that walks across your screen and talks to Claude Code from a retro terminal popover.

> ⚠️ Community port. The original macOS/Swift app, the character "Rocky," and
> **all sprite assets** are the work of **@itmesneha**. All credit for the concept,
> art, and behaviors goes to her. This repo only re-implements the runtime on
> Windows in Python + PyQt6, plus a few extras (voice, MCP assistant tools).
>
> Original repo: <https://github.com/itmesneha/agentrocky>

## What it does

Rocky is Rocky, Our favorite buddy in the movie/book Project Hail Mary:

- Walks across your screen above the taskbar, bounces at edges, breaks into jazz.
- Pops a retro green-on-black terminal popover when you click him.
- Talks to **Claude Code** through that terminal — color-coded assistant text,
  tool calls, errors. Stream-json parsing.
- Shows speech bubbles on tool use / turn end.
- Plays Rocky voice clips on lifecycle events (start, done, error, idle, etc.). AMAZE AMAZE AMAZE
- Exposes four MCP tools so Claude can set reminders, take notes, open URLs/files,
  and launch whitelisted desktop apps.

## Install (non-tech, no Python needed)

Grab the latest zip from
[**Releases**](https://github.com/KMercad0/agentrocky-windows/releases),
unzip, double-click `setup.bat`. It installs the Claude CLI, logs you in,
walks you through dropping the 6 sprite PNGs in. Done.

Full step-by-step + troubleshooting: [How-to-Run-rocky.md](./How-to-Run-rocky.md).

## Requirements

- Windows 10 / 11
- Python 3.10+ (only if running from source — release zip has its own runtime)
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) installed and
  authenticated (`claude login` once — `setup.bat` does this for you)
- The 6 sprite PNGs from the original repo (not redistributed here)

## Setup

```bash
git clone <this-repo-url>
cd agentrocky-windows

pip install -r requirements.txt

npm install -g @anthropic-ai/claude-code
claude login
```

Then copy the 6 PNG sprites from
[itmesneha/agentrocky](https://github.com/itmesneha/agentrocky)'s
`Assets.xcassets` into `./sprites/`:

```
sprites/stand.png
sprites/walkleft1.png
sprites/walkleft2.png
sprites/jazz1.png
sprites/jazz2.png
sprites/jazz3.png
```

Sprites are **not redistributed** here out of respect for the original author.

## Run

```bash
pythonw rocky.py
```

`pythonw.exe` hides the console. Right-click rocky (or the tray icon) for
**Show Chat / Hide / Restart Claude / Voice / Pause Walk / Quit**.

Global hotkey: **Ctrl+Alt+R** summons the chat from anywhere.

Prebuilt-exe route, source route, and troubleshooting:
[How-to-Run-rocky.md](./How-to-Run-rocky.md).

## Build (PyInstaller)

```bash
pyinstaller mcp_server.spec --noconfirm
pyinstaller rocky.spec --noconfirm
```

Output layout — onedir for `rocky` (cold start ~3-5× faster than onefile),
onefile for the MCP sidecar:

```
dist/
  mcp_server.exe          ← onefile sidecar (~21 MB)
  rocky/
    rocky.exe             ← launcher (~3 MB)
    _internal/...         ← Qt + Python runtime (~99 MB)
```

To distribute: copy `dist/mcp_server.exe` next to `dist/rocky/rocky.exe`,
drop the 6 sprite PNGs into `dist/rocky/sprites/`, zip the `rocky/` folder.

`mcp_server.exe` must sit next to `rocky.exe`. The MCP config written at
startup (`~/.agentrocky/mcp_config.json`) points `claude --mcp-config` at
`Path(sys.executable).parent / "mcp_server.exe"`.

The exe is **unsigned**. Windows SmartScreen will warn on first launch — click
*More info → Run anyway*. Code signing is on the roadmap.

Full step-by-step including troubleshooting: [How-to-Run-rocky.md](./How-to-Run-rocky.md).

## Safety

Rocky launches `claude` with `--dangerously-skip-permissions`. Claude can run
shell commands, edit files, and call tools without per-action prompts.
Mitigations in this port:

- Claude's cwd is sandboxed to `~/agentrocky-workspace/` (override with
  `AGENTROCKY_CWD`).
- First send each session shows a confirmation dialog.
- `~/.agentrocky/audit.log` records every `user_send` and `tool_use` (no
  assistant text, no results).
- `rocky.open` only opens URLs or files inside the workspace.
- `rocky.launch_app` is gated by a hardcoded executable whitelist.

If you don't want autonomous tool execution, don't use this app.

## Personal assistant tools (V3)

Rocky exposes four MCP tools that Claude calls from chat:

| Tool | What it does |
|---|---|
| `rocky.reminder` | Schedule one-shot toast + voice clip. *"remind me in 30 minutes to stretch"* |
| `rocky.note` | Append timestamped line to `~/agentrocky-workspace/notes.md` |
| `rocky.open` | Open URL or file inside the workspace |
| `rocky.launch_app` | Spawn whitelisted app: notepad, calc, explorer, cmd, paint, wordpad, word, excel, powerpoint, outlook, chrome, edge, firefox |

Reminders persist in `~/.agentrocky/reminders.json`. Missed-by-<1h fire on next
launch; older drop. **Rocky must be running for reminders to fire** —
schtasks integration is V3.5.

## Architecture

Single file: `rocky.py`. Plus `mcp_server.py` (stdio MCP sidecar).

- **`Rocky`** — frameless transparent always-on-top widget; 30 fps move + 8 fps
  walk-cycle timers.
- **`ChatWindow`** — frameless dark popover, `QTextEdit` output + `QLineEdit`
  input, draggable header, ↑/↓ history, Esc to close, Ctrl+L to clear, token
  counter.
- **`ClaudeSession`** — persistent `claude` subprocess in stream-json mode.
  Daemon threads read stdout/stderr; cross-thread updates via `pyqtSignal`.
- **`ReminderManager`** — `QFileSystemWatcher` on `reminders.json` → `QTimer`
  fires → native Win10/11 toast + voice clip.
- **`mcp_server.py`** — exposes the four tools to Claude via `--mcp-config`.

```
[Rocky GUI]  ── stdin →  [claude.exe]  ── HTTPS ──▶ Anthropic API
              ← stdout ─       │
              ← stderr ─       │ stdio
                               ▼
                       [mcp_server.py]
```

## Differences from the original

- Windows-native: PyQt6 instead of SwiftUI; tray icon + right-click menu for
  quit (no macOS app menu).
- Single-instance lock via `QSharedMemory`.
- Multi-monitor + High-DPI aware; hides on Win+L lock screen.
- Workspace sandbox + audit log.
- Voice pack on lifecycle events.
- MCP assistant tools (reminder / note / open / launch_app).
- Crash recovery via global excepthook → `~/.agentrocky/log.txt`.

Behavior parity (walk speed, jazz timing, bubble messages, stream-json colors)
follows the original spec.

## Credits

- **Original concept, character, art, and macOS app:**
  [@itmesneha](https://github.com/itmesneha) —
  <https://github.com/itmesneha/agentrocky>
- **Voice clips (Rocky sounds):**
  [@Akshat1903](https://github.com/Akshat1903) —
  [rocky-peon-ping](https://github.com/Akshat1903/rocky-peon-ping),
  licensed CC-BY-NC-4.0. Voice references Rocky from Andy Weir's
  *Project Hail Mary*. **Non-commercial use only.** Toggle via tray menu or
  right-click rocky → **Voice**.
- **Windows port:** this repo. Built with PyQt6.

If you like the project, ⭐ the **original repo** first:
<https://github.com/itmesneha/agentrocky>.

## License

Code in this repo: MIT (see `LICENSE`). **Sprite assets are not included** and
remain under the original author's terms — fetch them from the upstream repo
and follow her license. Voice clips under CC-BY-NC-4.0 (see
`sounds/LICENSE-VOICE.md`).
