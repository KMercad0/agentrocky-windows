# agentrocky Windows port — Features V1

This doc tracks **post-improvement-plan** features. The original `improvement_plan.md`
covered hardening (P0–P3). This doc covers new capabilities: voice, live TTS, and
tool integrations (alarms, calendar, etc.).

---

## Status snapshot

| Feature | Phase | Status |
|---|---|---|
| Voice pack — lifecycle SFX | V1 | 📋 planned (this doc) |
| Live TTS — voice Claude's replies | V2 | ⏳ deferred until V1 stable |
| Tool integrations (MCP: reminder / note / open) | V3 | 📋 planned (this doc) |
| Calendar + reliable alarms | V3.5 | ⏳ deferred (auth flow) |

---

# V1 — Rocky voice pack (lifecycle SFX)

## Context
agentrocky currently signals lifecycle events (session ready, user send, task
complete, errors) via speech bubbles + jazz dance. User wants Rocky to actually
*talk*. Compared two CC-BY-NC repos:

- **rocky-peon-ping** (Akshat1903) — 56 pre-rendered Rocky-PHM voice clips across
  6 categories. Playback only, no TTS deps, ~0ms latency.
- **rocky-tts** (Kuberwastaken) — full Coqui YourTTS / XTTS-v2 / RVC engine.
  ~3GB install, 2-22s latency, voices arbitrary text.

V1 picks **Lite** scope (peon-ping only) and **vendor WAVs** into repo.
Rationale: peon-ping covers ~80% of perceived "Rocky talks" UX for ~5% of effort,
no PyTorch install, ships in a day. Live TTS for Claude's replies = V2.

## Target files

| File | Change |
|---|---|
| `rocky.py` | new `VoicePack` class, signal hookups, tray + context-menu toggle |
| `README.md` | voice-pack credits + license attribution |
| `sounds/` (new dir) | vendored 56 WAVs + `manifest.json` + `LICENSE-VOICE.md` |
| `improvement_plan.md` | add P4 entry "voice pack — done" |

`.gitignore` is **not** modified — `sounds/` ships in repo (CC-BY-NC permits
redistribution with attribution; contrast with `sprites/` which has no public
license and is intentionally excluded).

## Design

### Asset layout
```
sounds/
  manifest.json                  # adapted from openpeon.json
  LICENSE-VOICE.md               # CC-BY-NC-4.0 + attribution chain
  session_start_01.wav … _08.wav
  task_acknowledge_01.wav … _08.wav
  task_complete_01.wav … _09.wav
  task_error_01.wav … _08.wav
  input_required_01.wav … _08.wav
  user_spam_01.wav … _09.wav
  resource_limit_01.wav … _08.wav
```

Source of truth: clone rocky-peon-ping, copy `rocky_pack/sounds/*.wav` and
`rocky_pack/openpeon.json` → `manifest.json`. Filename scheme normalized at
copy time so manifest stays minimal.

### `VoicePack` class (rocky.py)
~40 lines. Stdlib only — no new pip deps.

```python
import winsound  # stdlib, win32 only

SOUND_DIR = Path(__file__).parent / "sounds"

class VoicePack:
    """Lifecycle SFX. Random clip per category. winsound playback (async)."""
    def __init__(self, base: Path) -> None:
        self.base = base
        self.enabled = sys.platform == "win32"
        self.by_category: dict[str, list[Path]] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        m = self.base / "manifest.json"
        if not m.exists():
            self.enabled = False
            return
        try:
            data = json.loads(m.read_text("utf-8"))
        except Exception:
            self.enabled = False
            return
        for entry in data.get("clips", []):
            cat = entry.get("category")
            f = self.base / entry.get("file", "")
            if cat and f.exists():
                self.by_category.setdefault(cat, []).append(f)

    def play(self, category: str) -> None:
        if not self.enabled:
            return
        clips = self.by_category.get(category)
        if not clips:
            return
        winsound.PlaySound(str(random.choice(clips)),
                           winsound.SND_FILENAME | winsound.SND_ASYNC)

    def stop(self) -> None:
        if sys.platform == "win32":
            winsound.PlaySound(None, 0)

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()
        return self.enabled
```

### Signal hookups (in `Rocky.__init__`)

| Existing signal | Voice category | Notes |
|---|---|---|
| `session.ready` | `session_start` | one-shot per launch (gated by `_claude_ready` flip) |
| `chat.submitted` | `task_acknowledge` | wire from `_on_user_send` |
| `session.task_complete` | `task_complete` | in `_on_task_complete`, alongside bubble + jazz |
| `session.session_died` | `task_error` | in `_on_session_died`, alongside chat error line |
| `line_received(_, "error")` | (skip) | too noisy; `session_died` covers fatal case |

`tool_use` deliberately **not** voiced — would spam on multi-tool turns. Bubble
already covers it.

### Tray + context-menu toggle
Add to `_build_tray` menu and `_show_context_menu`:
```python
voice_action = menu.addAction("Voice: On")
def _toggle():
    on = rocky.voice.toggle()
    voice_action.setText(f"Voice: {'On' if on else 'Off'}")
voice_action.triggered.connect(_toggle)
```
Per-launch state only — no `QSettings` persistence in V1.

### Lock-screen + quit cleanup
- `Rocky._tick_lock_state` → also call `self.voice.stop()` on lock so an
  in-flight clip doesn't bleed past screen lock.
- `app.aboutToQuit.connect(rocky.voice.stop)` → silence on exit.

## Existing utilities reused
- `random.choice` (already imported)
- `json.loads` (already imported)
- `pathlib.Path` (already imported)
- `QMenu.addAction` pattern (used 8× in tray + context menu)
- `Rocky._claude_ready` flag — already gates first-send
- Existing signal-connect pattern in `Rocky.__init__` (lines ~638-645)

No new imports beyond `winsound`.

## Verification

End-to-end smoke (Windows):
1. `pythonw rocky.py`
2. ~3s after launch → audible *"Rocky here. Ready work, question?"* or similar
3. Open chat, send any message → immediate ack clip (e.g. *"Yes yes yes!"*)
4. Wait for Claude `result` → *"Done done done! Fist bump!"*
5. Tray → right-click → **Voice: On** toggle → label flips to **Voice: Off**
6. Send another message → silent; toggle back → audible
7. Right-click rocky → context menu also offers Voice toggle
8. Force session death: `taskkill /IM claude.exe /F` → error clip plays
9. **Win+L** → lock; mid-play clip cuts; on unlock no leftover audio
10. Tray → Quit → no orphan audio, no orphan `claude.exe`
11. `git status` → `sounds/*.wav`, `sounds/manifest.json`,
    `sounds/LICENSE-VOICE.md`, `rocky.py`, `README.md`,
    `improvement_plan.md` modified/added; `sprites/` still untracked
12. README on GitHub → credits section visible with links to @Akshat1903 and
    @itmesneha

## License attribution

`sounds/LICENSE-VOICE.md`:
```
Voice pack: rocky-peon-ping by Akshat1903
Source:     https://github.com/Akshat1903/rocky-peon-ping
License:    CC-BY-NC-4.0  https://creativecommons.org/licenses/by-nc/4.0/

Voice references the character "Rocky" from Andy Weir's novel
"Project Hail Mary". Non-commercial use only. Attribution required.

Generated via Coqui YourTTS zero-shot voice cloning.
```

`README.md` — new section under existing **Credits**:
```markdown
### Voice (optional, Windows only)

Lifecycle voice clips are vendored from
[rocky-peon-ping](https://github.com/Akshat1903/rocky-peon-ping) by
[@Akshat1903](https://github.com/Akshat1903), CC-BY-NC-4.0. The voice
references Rocky from Andy Weir's *Project Hail Mary* — **non-commercial use only**.
Toggle on/off via tray menu or right-click rocky → Voice.
```

## V1 risks / unknowns
- Category file count assumed from manifest summary; copy step uses
  `glob("*.wav")` to be robust.
- `input_required`, `user_spam`, `resource_limit` categories have no natural
  hook today. Files ship anyway (cheap), available for future hooks.
- winsound `SND_ASYNC` plays one sound at a time. Rapid event sequence (send →
  ack → result within 200ms) clips the ack. Acceptable.

---

# V2 — Live TTS for Claude's replies (deferred)

Stretch goal once V1 is stable. Voices Claude's actual assistant text via
Kuber's [rocky-tts](https://github.com/Kuberwastaken/rocky-tts) engine.

## Sketch

| Dimension | V2 plan |
|---|---|
| Engine | Coqui YourTTS (default) — best latency/quality tradeoff |
| Process model | Separate `rocky-tts --server` Python process; agentrocky talks to it via HTTP / pipe |
| Trigger | `gate via env var`: `AGENTROCKY_TTS=full` (default `off`) |
| Hook | `session.line_received(text, "text")` → enqueue TTS job |
| Streaming | Speak per assistant text chunk, not after full result |
| Hardware | CPU works (~2s latency); GPU much faster |
| Disk | ~3GB models on first run |
| License | CC-BY-NC-4.0 (same chain as V1) |

## Things to figure out before V2
- IPC: HTTP server (rocky-tts has one) vs. stdin pipe vs. subprocess-per-call.
  Server mode keeps model warm. Pick HTTP, localhost only.
- Queueing: Claude can stream multiple text blocks per turn. Need queue with
  drop-old-on-new-message semantics (don't pile up audio).
- Annoyance budget: long replies = wall of speech. Mitigations: cap at first
  N words, or detect code blocks and skip them, or only speak first paragraph.
- Coexistence with V1: SFX (Rocky-fast events) vs. TTS (Rocky-slower paragraphs).
  Likely play V1 SFX *before* speaking, or duck/skip if TTS busy.
- Install UX: don't auto-pull 3GB. Tray action **"Enable voice (download
  models, ~3GB)"** that confirms, then runs `pip install` + first-run model fetch.
- Bundling vs depend: keep rocky-tts external. Document install steps.

## Out of scope for V2
- RVC (Retrieval Voice Conversion) variant — heavier, niche
- XTTS-v2 cold-start path (22s) — only YourTTS in V2
- Non-Windows backends

---

# V3 — Tool integrations (rocky as MCP server)

## Decisions
1. **Architecture: MCP**. agentrocky exposes typed tools via Anthropic's MCP
   protocol. Claude (subprocess) calls them. No `claude mcp add` from user —
   agentrocky writes `~/.agentrocky/mcp_config.json` and passes
   `--mcp-config` to its claude subprocess at launch. Self-contained.
2. **Starter tool set**: `reminder`, `note`, `open`. All bounded.
3. **Calendar**: deferred (see V3.5 below).
4. **Reminder persistence**: persisted JSON + requeue on launch. Pair with
   improvement #35 (autostart) so reminders fire reliably.

## Why MCP over alternatives
| Path | Verdict |
|---|---|
| Let Claude shell `schtasks` (today) | Works but token-heavy per call, no native UI integration, no audit trail beyond bash logs. |
| **MCP server (chosen)** | Typed schemas → Claude picks args correctly first try. Native toast UI. Reusable across any MCP-aware client. ~150-200 LOC. |
| In-chat slash commands (`/reminder ...`) | Zero tokens but no natural language. Off-brand for "chat with rocky". |

## Target files (additions)

| File | Change |
|---|---|
| `rocky.py` | spawn MCP server (in-process thread or sidecar process); pass `--mcp-config` to claude subprocess; toast handler |
| `mcp_server.py` (new) | MCP protocol implementation; tool handlers for `rocky.reminder`, `rocky.note`, `rocky.open` |
| `~/.agentrocky/mcp_config.json` (runtime) | written on launch, points claude at the local MCP server |
| `~/.agentrocky/reminders.json` (runtime) | persistent reminder queue |
| `~/agentrocky-workspace/notes.md` (runtime) | append-only notes file |
| `requirements.txt` (new or updated) | `mcp` (Anthropic Python SDK), `winrt-Windows.UI.Notifications` for toasts |

## Tools — schemas + bounds

### `rocky.reminder`
```jsonc
{
  "name": "reminder",
  "description": "Schedule a one-shot toast notification.",
  "inputSchema": {
    "type": "object",
    "required": ["text", "when"],
    "properties": {
      "text": {"type": "string", "maxLength": 200},
      "when": {
        "type": "string",
        "description": "ISO 8601 timestamp OR duration like '5m', '2h', '1d'"
      }
    }
  }
}
```
Handler: parse `when`, schedule `QTimer.singleShot`, append to
`~/.agentrocky/reminders.json`. On fire: Windows toast via `winrt`. Removes
itself from JSON on dismiss.

**Bound**: text capped at 200 chars; `when` parsed with whitelist regex
(`\d+[smhd]` or ISO 8601). No fs/network access.

### `rocky.note`
```jsonc
{
  "name": "note",
  "description": "Append a timestamped line to the user's notes file.",
  "inputSchema": {
    "type": "object",
    "required": ["text"],
    "properties": {"text": {"type": "string", "maxLength": 2000}}
  }
}
```
Handler: open `~/agentrocky-workspace/notes.md` in append mode, write
`[timestamp] text\n`. Returns confirmation.

**Bound**: hardcoded path inside WORKSPACE. No directory traversal possible.

### `rocky.open`
```jsonc
{
  "name": "open",
  "description": "Open a URL in the default browser, or a file inside the agentrocky workspace.",
  "inputSchema": {
    "type": "object",
    "required": ["target"],
    "properties": {"target": {"type": "string"}}
  }
}
```
Handler: validate target with allowlist:
- `http://` or `https://` URL → `os.startfile(target)` (delegates to default browser)
- absolute path that is inside `WORKSPACE` (resolve + check `Path.is_relative_to`) → `os.startfile`
- everything else → return error string, do nothing

**Bound**: rejects arbitrary exes, system paths, `file://` tricks, UNC paths,
relative paths that escape WORKSPACE.

## Reminder persistence + lifecycle

```python
# on rocky launch:
for r in load_reminders():
    if r.fire_at <= now:
        # missed window — fire immediately if recent (<1h) else drop
        if now - r.fire_at < timedelta(hours=1):
            fire(r)
        drop(r)
    else:
        schedule(r)

# on schedule:
QTimer.singleShot((r.fire_at - now).total_seconds() * 1000, lambda: fire(r))

# on fire:
toast(r.text)
remove_from_json(r.id)
voice.play("session_start")  # reuse a Rocky-says-something clip
```

JSON shape:
```json
[
  {"id": "uuid", "text": "wake up", "fire_at": "2026-04-29T05:00:00Z",
   "created_at": "2026-04-28T22:00:00Z"}
]
```

UX caveat documented in README: **rocky must be running at fire time.**
Recommend pairing with autostart (improvement #35).

## Auto-registering MCP server with claude

```python
# in rocky.py main(), before session.start():
mcp_cfg = AUDIT_DIR / "mcp_config.json"
mcp_cfg.write_text(json.dumps({
    "mcpServers": {
        "agentrocky": {
            "command": sys.executable,
            "args": [str(Path(__file__).parent / "mcp_server.py")]
        }
    }
}))
# pass --mcp-config <mcp_cfg> to claude subprocess argv
```
Claude CLI picks up the local config. No global registration.

## Toast on Windows

Two viable libs:
- `winrt-Windows.UI.Notifications` — native, modern, requires Win10+
- `win10toast` — pip-only wrapper, simpler API, less polish

Pick `winrt` for native fidelity. Falls back to `QSystemTrayIcon.showMessage`
if `winrt` import fails.

## Audit
Every MCP tool call → existing `audit()` plumbing with `kind="mcp_tool"`.
Reuses `~/.agentrocky/audit.log`.

## Verification

1. `pythonw rocky.py` → check `~/.agentrocky/mcp_config.json` exists
2. In chat: *"rocky remind me in 30 seconds to test"* → Claude calls
   `rocky.reminder` → toast fires after 30s + clip plays
3. Chat: *"rocky note: bought milk"* → `notes.md` has timestamped line
4. Chat: *"rocky open https://github.com/itmesneha/agentrocky"* → browser opens
5. Chat: *"rocky open C:/Windows/System32/cmd.exe"* → tool returns error,
   nothing launches
6. Set reminder for 1h ahead, quit rocky, relaunch within 1h → reminder
   re-scheduled (check `tasklist` for QTimer or just wait)
7. `~/.agentrocky/audit.log` has `mcp_tool` entries
8. Force-quit (Task Manager kill) → on next launch, missed reminder within
   1h grace fires immediately; older ones dropped

## Out of scope for V3
- Calendar (Outlook/Google/Graph) — see V3.5
- Cross-device sync
- Mobile push
- Email
- Recurring reminders (daily, weekly) — V3a only does one-shot
- `schtasks` integration for "fires even if rocky off" — see V3.5

---

# V3.5 — Calendar + reliable alarms (future)

Deferred until V3 ships and stabilizes.

## Calendar
Three backends, pick one based on user setup:
- **Outlook COM** — `pywin32`, no auth, only works if Outlook desktop installed
- **Google Calendar API** — OAuth 2.0 flow, ~100 LOC just for token dance
- **Microsoft Graph** — OAuth 2.0, modern, works for both personal + business

Prefer **Microsoft Graph** for breadth + future-proof. Auth = device-code flow
(user opens browser, pastes code, agentrocky stores refresh token in
`~/.agentrocky/`).

## Reliable alarms (fire even if rocky off)
On `rocky.reminder` create:
- Schedule QTimer (in-process, fires if rocky running)
- Also `schtasks /create` with a one-shot trigger that runs
  `pythonw rocky_reminder_fire.py <id>` at fire time
- On fire: dedup (whichever fires first wins), other unregisters

Adds `schtasks` cleanup logic + reboot edge cases. Worth deferring.

---

## Cross-cutting future items
- Pyinstaller single-exe (improvement #34, deferred)
- Autostart registry toggle (improvement #35, deferred — pairs well with V3
  reminder persistence)
- macOS / Linux ports (currently win32-only)
- V2 Live TTS — see above

---

## Cross-cutting future items
- Pyinstaller single-exe (improvement #34, deferred)
- Autostart registry toggle (improvement #35, deferred)
- macOS / Linux ports (currently win32-only)


## new features
- occational check in of rocky i.e Have you drink any water yet. question?, have you stretched yet question? basically health checks. mental and physical.