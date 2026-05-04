# agentrocky-windows

> **Rocky:** Hello, friend! I am Rocky. Question, friend — you have Windows
> computer? Good good good. I live there now. Walk on screen. Help with
> work. Amaze!
>
> **Grace:** What Rocky's trying to say: this is an **unofficial Windows port**
> of [**agentrocky**](https://github.com/itmesneha/agentrocky) by
> [**@itmesneha**](https://github.com/itmesneha) — a desktop pixel-art
> companion that walks across your screen and talks to Claude Code from a
> retro terminal popover.
>
> **Rocky:** Grace make me sound like science project. I am friend. Fist my bump!

> ⚠️ Community port. The original macOS/Swift app, the character "Rocky," and
> **all sprite assets** are the work of **@itmesneha**. All credit for the
> concept, art, and behaviors goes to her. This repo only re-implements the
> runtime on Windows in Python + PyQt6, plus a few extras (voice, MCP
> assistant tools).
>
> Original repo: <https://github.com/itmesneha/agentrocky>

## What Rocky does

> **Rocky:** I tell you! Things I do:
>
> - Walk on screen above taskbar. Bounce at edges. Sometimes break into
>   jazz dance. *Amaze Amaze Amaze!*
> - Click me — small green terminal pop up. We chat. I talk to Claude Code.
> - Speech bubble when tool use, when task done. So you know what happen.
> - Voice clips for events. Start, done, error. *Happy! Sad! Brain tired!*
> - Four MCP tools so Claude help you: set reminder, take note, open file,
>   launch app.
> - Health check-ins! Every X minutes I ask: drink water, question?
>   Stretch, question? Eye tired, question? *Caring friend!*
>
> **Grace:** Stream-json parsing for the chat output, color-coded by message
> type. Speech bubbles fire on `tool_use` and turn-end events. The MCP
> sidecar (`mcp_server.py`) exposes the four tools over stdio.

## Install — easy way (no Python)

> **Grace:** If you're not a developer, this is the path. Download a zip,
> double-click one file, you're done.
>
> **Rocky:** I do hard work for you. You drink coffee. Good!

1. Grab the latest zip from
   [**Releases**](https://github.com/KMercad0/agentrocky-windows/releases).
2. Unzip anywhere — Desktop is fine.
3. Double-click **`setup.bat`** inside the unzipped folder.

`setup.bat` installs the Claude CLI, signs you in, walks you through dropping
the 6 sprite PNGs in, then launches Rocky.

Full walk-through with screenshots-style detail and troubleshooting:
[How-to-Run-rocky.md](./How-to-Run-rocky.md).

## Requirements

> **Rocky:** What you need before I come live with you?

- Windows 10 or 11
- Anthropic account (for `claude login`)
- Node.js (only if you don't have it — `setup.bat` will tell you)
- Python 3.10+ — only if running from source. Release zip has its own.
- The 6 sprite PNGs from the original repo (not redistributed here — see
  [Credits](#credits))

## Run from source (developers)

> **Grace:** Cloning the repo, classic dev workflow.
>
> **Rocky:** Words I do not understand. Continue.

```bash
git clone https://github.com/KMercad0/agentrocky-windows
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

Run:

```bash
pythonw rocky.py
```

> **Rocky:** `pythonw.exe` hide console. No black box. Clean!
>
> **Grace:** Right-click Rocky (or the tray icon) for **Show Chat / Hide /
> Restart Claude / Voice / Pause Walk / Quit**. Global hotkey **Ctrl+Alt+R**
> summons the chat from anywhere.

## Build the exe yourself

> **Grace:** PyInstaller bundles everything into a self-contained folder.
>
> **Rocky:** I become tiny computer file. Travel anywhere.

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
copy `setup.bat` next to it too, drop the 6 sprite PNGs into
`dist/rocky/sprites/` *(skip the sprites if shipping a release zip — users
fetch them via setup.bat)*, then zip the `rocky/` folder.

`mcp_server.exe` must sit next to `rocky.exe`. The MCP config written at
startup (`~/.agentrocky/mcp_config.json`) points `claude --mcp-config` at
`Path(sys.executable).parent / "mcp_server.exe"`.

> **Rocky:** *Bad Bad Bad* if you move rocky.exe away from `_internal\`!
> Computer cry. Python DLL not load.
>
> **Grace:** Yeah. Keep the folder intact.

The exe is **unsigned**. Windows SmartScreen will warn on first launch — click
*More info → Run anyway*. Code signing is on the roadmap.

Full step-by-step + troubleshooting: [How-to-Run-rocky.md](./How-to-Run-rocky.md).

## Safety

> **Grace:** This is the part I want you to actually read. Rocky launches
> `claude` with `--dangerously-skip-permissions`. Claude can run shell
> commands, edit files, and call tools without per-action prompts.
>
> **Rocky:** Big trust. Big responsibility. Like fistbump but with computer.

Mitigations in this port:

- Claude's cwd is sandboxed to `~/agentrocky-workspace/` (override with
  `AGENTROCKY_CWD`).
- First send each session shows a confirmation dialog.
- `~/.agentrocky/audit.log` records every `user_send` and `tool_use` (no
  assistant text, no results).
- `rocky.open` only opens URLs or files inside the workspace.
- `rocky.launch_app` is gated by a hardcoded executable whitelist.

If you don't want autonomous tool execution, don't use this app.

## Personal assistant tools

> **Rocky:** Claude can ask me for help. I do four things:

| Tool | What it does |
|---|---|
| `rocky.reminder` | Schedule one-shot toast + voice clip. *"remind me in 30 minutes to stretch"* |
| `rocky.note` | Append timestamped line to `~/agentrocky-workspace/notes.md` |
| `rocky.open` | Open URL or file inside the workspace |
| `rocky.launch_app` | Spawn whitelisted app: notepad, calc, explorer, cmd, paint, wordpad, word, excel, powerpoint, outlook, chrome, edge, firefox |

> **Rocky:** Reminder live in `~/.agentrocky/reminders.json`. Miss by less
> than one hour, I still fire next time you open me. Older — gone. *Sad sad
> sad.*
>
> **Grace:** Schtasks integration for true persistence is V3.5 on the
> roadmap.

## Health check-ins

> **Rocky:** Different from reminders. Reminder is one time — Claude tell me
> *"poke human in 30 minute about stretch"*, I poke once, done. Health
> check-in is **forever poke**. Every X minutes I check on you. Drink water,
> question? Stretch, question? Look far thing, question?
>
> **Grace:** Local recurring nudges, no Claude involved. Five built-in
> categories with sensible defaults; toggle them per-category from the tray
> menu under **Health Check-ins**.

| Category | Default interval | Jitter | Default state |
|---|---|---|---|
| `water`   | 60 min  | ±10 min | on  |
| `stretch` | 90 min  | ±15 min | on  |
| `eyes`    | 20 min  | ±5 min  | on  (20-20-20 rule) |
| `posture` | 45 min  | ±10 min | off |
| `mental`  | 120 min | ±20 min | on  |

When a check-in fires:

1. Native Win10/11 toast pops with the category copy (e.g. *"rocky thirsty.
   human drink water, question?"*).
2. Rocky plays a category-appropriate voice clip.
3. A speech bubble shows on the sprite.

> **Rocky:** I do not nag. Each category has *jitter* — small randomness so
> I do not poke you at exactly the same minute every day. Less annoying.
> *Good engineer.*

### Configure

- Tray icon → right-click → **Health Check-ins** submenu:
  - **Master enable** — global on/off
  - Per-category toggles (e.g. *Water (60m)* — click to flip)
  - **Edit health.json…** — opens `~/.agentrocky/health.json` in your
    default editor for fine-tuning intervals, jitter, and copy text

### Config file

`~/.agentrocky/health.json`:

```json
{
  "enabled": true,
  "categories": {
    "water":   { "enabled": true,  "interval_min": 60,  "jitter_min": 10,
                 "copy": "rocky thirsty. human drink water, question?" },
    "stretch": { "enabled": true,  "interval_min": 90,  "jitter_min": 15,
                 "copy": "rocky stiff. human stretch, question?" },
    "eyes":    { "enabled": true,  "interval_min": 20,  "jitter_min": 5,
                 "copy": "eye tired. human look far thing 20 second, question?" },
    "posture": { "enabled": false, "interval_min": 45,  "jitter_min": 10,
                 "copy": "rocky see slouch. human sit straight, question?" },
    "mental":  { "enabled": true,  "interval_min": 120, "jitter_min": 20,
                 "copy": "rocky check human mood. human ok, question?" }
  }
}
```

Edit, save — `QFileSystemWatcher` picks up the change live, no restart
needed. Add your own categories the same way (just match the schema).

> **Grace:** Reminders vs. health check-ins, quick mental model:
>
> | | Reminders | Health check-ins |
> |---|---|---|
> | Set by | Claude (via `rocky.reminder` MCP tool) | You — tray menu / config file |
> | Fires | Once at a specific time | Recurring on interval |
> | Stored in | `reminders.json` | `health.json` |
> | Survives Rocky restart | Missed-by-<1h refire | Always (recomputes next fire) |

## Architecture

> **Grace:** Quick map for anyone reading the code.
>
> **Rocky:** This is for science people. Skip if you just want me to walk.

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

> **Rocky:** Sneha original is Mac. I am Windows version. Different bones,
> same heart.

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

> **Rocky:** Important. Listen.

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

> **Rocky:** If you like project, star **original repo first**:
> <https://github.com/itmesneha/agentrocky>. Sneha make me. I am her work.
> Respect.
>
> **Grace:** Yeah, what he said.

## License

Code in this repo: MIT (see `LICENSE`). **Sprite assets are not included** and
remain under the original author's terms — fetch them from the upstream repo
and follow her license. Voice clips under CC-BY-NC-4.0 (see
`sounds/LICENSE-VOICE.md`).

> **Rocky:** Now go. Install me. We work together. *Amaze Amaze Amaze!*
