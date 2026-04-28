# agentrocky-windows

An **unofficial** Windows port of [**agentrocky**](https://github.com/itmesneha/agentrocky)
by [**@itmesneha**](https://github.com/itmesneha) — a desktop pixel-art companion
that walks across your screen and talks to Claude Code from a retro terminal popover.

> ⚠️ This is a community port. The original macOS/Swift app, the character "Rocky,"
> and **all sprite assets** are the work of **@itmesneha**. All credit for the
> concept, art, and behaviors goes to her. This repo only re-implements the runtime
> on Windows in Python + PyQt6.
>
> Original repo: <https://github.com/itmesneha/agentrocky>

## Demo

*(Demo recording coming soon.)*

## What it does

Rocky is a tiny pixel character who:

- Walks back and forth above your Windows taskbar.
- Bounces at screen edges, flipping his sprite when he turns.
- Pops a 420×520 retro green-on-black terminal when you click him.
- Talks to **Claude Code** through that terminal — color-coded output for assistant
  text (green), tool calls (cyan), and errors (red).
- Celebrates with a 2.4-second jazz dance when Claude finishes a task.
- Spontaneously breaks into jazz every 15–45 seconds when you're not chatting.
- Shows speech bubbles ("rocky thinking", "fist my bump", etc.) when Claude is
  using tools or finishes a turn.

All of the above is described in @itmesneha's [original README](https://github.com/itmesneha/agentrocky#readme)
— this Windows build mirrors that behavior.

## Requirements

- **Windows 10 / 11**
- **Python 3.10+**
- **[PyQt6](https://pypi.org/project/PyQt6/)**
- **[Claude Code CLI](https://docs.claude.com/en/docs/claude-code)** installed and
  authenticated (`claude login` once)
- The 6 sprite PNGs from the original repo (see below)

## Setup

```bash
# 1. Clone this repo
git clone <this-repo-url>
cd agentrocky-windows

# 2. Install PyQt6
pip install PyQt6

# 3. Install Claude Code (if you haven't)
npm install -g @anthropic-ai/claude-code
claude login

# 4. Add the sprites
#    Copy the 6 PNG assets from the original repo's
#    agentrocky/Assets.xcassets folder into ./sprites/ here.
#    Required filenames:
#      sprites/stand.png
#      sprites/walkleft1.png
#      sprites/walkleft2.png
#      sprites/jazz1.png
#      sprites/jazz2.png
#      sprites/jazz3.png
```

The sprites are **not redistributed** in this repo out of respect for the original
author. Please get them from <https://github.com/itmesneha/agentrocky>.

## Run

```bash
pythonw rocky.py
```

`pythonw.exe` (instead of `python.exe`) hides the console window — Rocky should
appear above your taskbar and start walking.

To stop him for now: **Task Manager → end `pythonw.exe`**. (A proper tray-icon
quit menu is on the [improvement plan](improvement_plan.md).)

## Safety warning

Rocky launches `claude` with `--dangerously-skip-permissions`. That means Claude
can run shell commands, edit files, and call tools **without asking for each
action**. The first time you send a message in a session, Rocky shows a
confirmation dialog — read it.

The current working directory passed to Claude is your **home folder** (`%USERPROFILE%`),
so Claude has read/write access to anything in there. The improvement plan moves
this to a sandboxed `~/agentrocky-workspace/` folder.

If you don't want autonomous tool execution, don't use this app — or fork it and
remove the flag.

## Architecture

Single file: `rocky.py` (~620 lines). Three main pieces:

- **`Rocky`** — frameless transparent always-on-top widget holding the sprite,
  driven by 60 fps movement and 8 fps walk-cycle timers.
- **`ChatWindow`** — frameless dark popover with a `QTextEdit` output and
  `QLineEdit` input. Header is draggable.
- **`ClaudeSession`** — wraps a persistent `claude` subprocess in stream-json
  mode. Daemon threads read stdout/stderr; cross-thread updates use `pyqtSignal`
  so the GUI thread is the only thing touching widgets.

```
[Rocky GUI]  ── stdin →  [claude.exe]  ── HTTPS ──▶ Anthropic API
              ← stdout ─
              ← stderr ─
   ▲
   pyqtSignal (queued, thread-safe)
```

## Differences from the original

| Area | Original (macOS/Swift) | This port (Windows/Python) |
|------|------------------------|----------------------------|
| Language / UI | Swift + SwiftUI | Python + PyQt6 |
| Window type | `NSPanel`, joins all Spaces | Qt frameless `Tool` window, current desktop only |
| Anchor | Above macOS Dock | ~50 px above Windows taskbar |
| Hide console | Native | `pythonw.exe` + `CREATE_NO_WINDOW` flag |
| Threading | Swift async + Combine | `threading.Thread` + `pyqtSignal` |
| Bubble shape | Custom SwiftUI `BubbleTail` | `QPainter` rounded rect + triangle tail |
| Quit affordance | macOS app menu | None yet (planned: tray icon) |

Behavior parity (walk speed, jazz timing, bubble messages, color codes,
stream-json parsing) follows the original spec.

## Roadmap

See [`improvement_plan.md`](improvement_plan.md) for the full list. P0 (next):

- System tray icon with **Quit** menu
- Kill the `claude` subprocess cleanly on quit
- Single-instance lock (no double-rocky)
- Drop the `[claude ready]` line from chat
- Audit log of user sends + tool uses (`~/.agentrocky/audit.log`)
- Sandbox cwd to `~/agentrocky-workspace/`

## Credits

- **Original concept, character, art, and macOS app:**
  [@itmesneha](https://github.com/itmesneha) —
  <https://github.com/itmesneha/agentrocky>
- **Windows port:** this repo. Built with PyQt6.

If you like the project, ⭐ the **original repo** first:
<https://github.com/itmesneha/agentrocky>.

## License

Code in this repo: see `LICENSE` (TBD — recommend matching the original repo's
license). **Sprite assets are not included** and remain under the original
author's terms — fetch them from the upstream repo and follow her license.
