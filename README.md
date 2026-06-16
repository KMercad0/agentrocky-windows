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

> ⚠️ Community project, not official — honestly more of a love letter than a
> product. The character "Rocky," the pixel art, and the original macOS app are
> all [**@itmesneha**](https://github.com/itmesneha)'s; that's the heart of it.
> This is a Windows rebuild (Python + PyQt6) with a few extras bolted on along
> the way — an offline mode, a couple of AI backends, voice, some wellness nags,
> an adjustable walk height. Sprites aren't redistributed here.
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
> - Five MCP tools so Claude help you: set reminder, take note, open file,
>   launch app, tune health check-ins.
> - Health check-ins! Every X minutes I ask: drink water, question?
>   Stretch, question? Eye tired, question? *Caring friend!*
>
> **Grace:** Stream-json parsing for the chat output, color-coded by message
> type. Speech bubbles fire on `tool_use` and turn-end events. The MCP
> sidecar (`mcp_server.py`) exposes the five tools over stdio.

## Install — easy way (one installer)

> **Grace:** If you're not a developer, this is the path. Download one file,
> click through it, and Rocky's walking on your screen. No Python, no Node, no
> copying files around.
>
> **Rocky:** I do hard work for you. You drink coffee. Good!

1. Grab **`RockySetup.exe`** from the
   [**Releases**](https://github.com/KMercad0/agentrocky-windows/releases) page.
2. Double-click it. Windows SmartScreen may warn (the installer is unsigned) —
   click **More info → Run anyway**.
3. Click through (installs to your user folder, no admin prompt). Done — Rocky
   walks.

Everything's bundled: the app, its runtime, and Rocky's sprites. On first run he
walks, dances, and nags you about water with **no AI backend and no cost**. Want
him to actually chat and do tasks? Add Claude or Gemini later — see
[Backends](#backends). That part is optional.

Full walk-through + troubleshooting: [How-to-Run-rocky.md](./How-to-Run-rocky.md).

## Requirements

> **Rocky:** What you need before I come live with you?

- Windows 10 or 11 — that's the only hard requirement. Rocky walks out of the box.
- **Optional, only if you want AI chat** (see [Backends](#backends)):
  - **Claude** — a paid Anthropic account + the Claude CLI (Rocky guides you).
  - **Gemini (free)** — Node.js + the Gemini CLI (Rocky guides you).
- Python 3.10+ — only if running from source, not the installer.

## Backends

> **Rocky:** Who put words in rocky brain? You choose.

Rocky talks to an AI backend, picked from the tray menu (right-click the tray
icon ▸ **Backend**). Your choice is remembered in
`~/.agentrocky/settings.json`.

| Backend | Needs | What you get |
|---|---|---|
| **None** | nothing | Rocky walks, does health check-ins, and holds a **scripted (no-AI) chat** — click a greeting, he replies in character and plays a voice clip. Fully usable, zero setup. |
| **Claude** | Claude CLI (`irm https://claude.ai/install.ps1 \| iex`, no Node) + `claude login` to a **paid** Anthropic account | **Safe by default** — chat + Rocky's own tools (reminders, notes, open, launch, health). Opt into **full access** (a skip-permissions coding agent) from the tray when you want it. |
| **Gemini (free)** | `@google/gemini-cli` + Google sign-in | **Chat + read-only** Rocky: talks in character and can read files to answer, but runs no commands and has no assistant tools (those are Claude-only). |

First launch starts on **None** — Rocky walks and nags you about water, no AI
and no cost until you choose a backend. Switch to Claude or Gemini any time from
the tray.

## Run from source (developers)

> **Grace:** Cloning the repo, classic dev workflow.
>
> **Rocky:** Words I do not understand. Continue.

```bash
git clone https://github.com/KMercad0/agentrocky-windows
cd agentrocky-windows

pip install -r requirements.txt

# optional — only if you want the Claude backend (no Node needed):
#   irm https://claude.ai/install.ps1 | iex   &&   claude login
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

To build the one-click installer, run `installer\build_installer.bat` — it builds
both exes, generates the icon, **bundles the sprites**, and emits
`installer\Output\RockySetup.exe`. (Manual zip alternative: copy
`dist/mcp_server.exe` next to `dist/rocky/rocky.exe`, drop the 6 sprite PNGs into
`dist/rocky/sprites/`, then zip the `rocky/` folder.)

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

> **Grace:** This is the part I want you to actually read.
>
> **Rocky:** Big trust. Big responsibility. Like fistbump but with computer.

Rocky ships **safe by default**. With the Claude backend, Claude starts in
**safe mode**: it has *no* shell and *no* arbitrary file access — only Rocky's
five MCP tools (set a reminder, take a note, open a workspace file, launch a
whitelisted app, tune health check-ins), each workspace-bounded and audited. In
safe mode Claude cannot run commands or read/change your files.

**Full access** turns Claude into a real coding agent: it runs with
`--dangerously-skip-permissions` and can execute arbitrary shell commands and
read or write any file your Windows account can. It is **opt-in** — enable it
from the tray menu (*Claude: Full access (skip permissions)*) and confirm the
warning; Rocky then restarts Claude with full power. The working directory
(`~/agentrocky-workspace/`, override `AGENTROCKY_CWD`) is only where Claude
*starts* — it is **not** a sandbox.

Mitigations in this port:

- Safe mode is the default; full access takes a deliberate opt-in + warning.
- The first message of each full-access session shows a confirmation dialog.
- `~/.agentrocky/audit.log` records every `user_send` and `tool_use` (no
  assistant text, no results).
- `rocky.open` only opens URLs or files inside the workspace;
  `rocky.launch_app` is gated by a hardcoded executable whitelist.
- `--strict-mcp-config` keeps your other personal MCP servers (Gmail, Drive,
  Calendar, …) out of Rocky's session entirely.

If you don't want autonomous tool execution, just leave full access off (the
default) — or use the Gemini / None backends.

## Personal assistant tools

> **Rocky:** Claude can ask me for help. I do five things:

| Tool | What it does |
|---|---|
| `rocky.reminder` | Schedule one-shot toast + voice clip. *"remind me in 30 minutes to stretch"* |
| `rocky.note` | Append timestamped line to `~/agentrocky-workspace/notes.md` |
| `rocky.open` | Open URL or file inside the workspace |
| `rocky.launch_app` | Spawn whitelisted app: notepad, calc, explorer, cmd, paint, wordpad, word, excel, powerpoint, outlook, chrome, edge, firefox |
| `rocky.health` | List or adjust the recurring health check-in categories (water / stretch / eyes / posture / mental) |

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
- **`mcp_server.py`** — exposes the five tools to Claude via `--mcp-config`.

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

- Windows-native: PyQt6 instead of SwiftUI; tray icon + right-click menu (no
  macOS app menu).
- A few AI backends to pick from: Claude, Gemini (free, read-only chat), and an
  offline None mode.
- A scripted no-AI chat in None mode — click a greeting, Rocky replies in
  character with voice, no backend needed.
- Voice clips on start / done / error and on reminders.
- Five little MCP assistant tools: reminder, note, open, launch_app, health.
- Health check-ins — five wellness categories (water / stretch / eyes /
  posture / mental), tray-configurable.
- Adjustable walk height — tray → *Set Walk Height* (a slider from the top of
  the screen down to the taskbar).
- A bit of safety around the agent: Claude safe-by-default (tools stripped to
  Rocky's own MCP set), opt-in full access behind a warning, audit log, strict
  MCP isolation, Gemini kept read-only.
- Single-instance lock, multi-monitor + High-DPI aware, hides on Win+L, crash
  recovery.

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
- **Windows version:** Karl Mercado
  ([@KMercad0](https://github.com/KMercad0/agentrocky-windows)) — rebuilt Rocky
  for Windows in Python + PyQt6 and tinkered along the way: a couple of backends,
  voice, the wellness nags, an adjustable walk height. The character, the art,
  and the whole idea are still [@itmesneha](https://github.com/itmesneha)'s.

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
