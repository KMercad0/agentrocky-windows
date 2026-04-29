# Plan: agentrocky Windows port — improvements

## Status snapshot (2026-04-28)
P0, P1, P2 shipped. P3 partial: crash log + high-DPI + lock-screen hide done.
Distribution items (PyInstaller, autostart) deferred to post-demo.

| Priority | Items | Status |
|---|---|---|
| P0 | 1, 3, 4, 5, 26, 27 | ✅ shipped |
| P1 | 9, 13, 14, 15, 17, 29 | ✅ shipped |
| P1 | 10 (cwd label) | ❌ reverted (user wanted plain `❯`) |
| P1 | 16 (auto-reconnect) | ⏳ partial — manual Restart via tray; no auto-retry |
| P2 | 2, 6, 7, 8, 11, 12, 18, 21, 24, 28 | ✅ shipped |
| P3 | 19, 23, 30 | ✅ shipped |
| P3 | 34, 35 | ⏳ deferred (post-demo) |
| P4 | Voice pack V1 (lifecycle SFX) | ✅ shipped — see `featuresV1.md` |
| Misc | 20, 22, 25, 31, 32, 33 | ⏳ open / skipped |

Per-item status is also marked inline below.

## Context
Initial port shipped (`rocky.py`, ~620 lines). Works end-to-end. This plan covers
hardening: closability, safety, performance, parity with original. User flagged
specifics: tray-quit, drop `[claude ready]`, single-instance guard. Plus broader
review covering UX, robustness, privacy, perf.

## Target file
`C:\Users\LarkLarkLark\Desktop\Workwork\claude_projects\agentrocky_windows\rocky.py`

Single file stays single file. No new modules.

---

## Full improvement list

### Closability / lifecycle
1. ✅ **System tray icon + Quit menu** — `QSystemTrayIcon` (using `stand.png` as icon), right-click menu: Show Chat / Hide Rocky / Restart Claude / Quit. Removes Task Manager dependency.
2. ✅ **Right-click rocky → context menu** — same actions inline. Faster than tray.
3. ✅ **Kill subprocess on quit** — `app.aboutToQuit.connect(session.stop)` → `proc.stdin.close()` + `proc.terminate()` + `wait(2s)` + `kill()` fallback.
4. ✅ **Single-instance lock** — `QSharedMemory` key `agentrocky-singleton-v1`. Second launch exits silently.

### Cosmetic / UX
5. ✅ **Drop `[claude ready]` line** — `ready` signal kept as internal flag + tray tooltip; chat stays clean.
6. ✅ **Esc closes chat** — `keyPressEvent` on ChatWindow.
7. ✅ **Ctrl+L clears terminal** — `output.clear()`.
8. ✅ **Up/Down arrow history** — `HistoryLineEdit` with draft preservation.
9. ✅ **Streaming `▋` cursor while running** — blink at 500ms between send and `result`.
10. ❌ **cwd basename in prompt label** — implemented then reverted; user preferred plain `❯` (more authentic to "chatting with rocky").
11. ✅ **Bubble word-wrap + max width** — `BUBBLE_MAX_WIDTH=280`, `TextWordWrap`.
12. ✅ **Pause idle jazz timer when chat open** — `idle_timer.stop()` on open, `_schedule_idle()` on close.

### Robustness
13. ✅ **Multi-monitor awareness** — `QGuiApplication.screenAt(QCursor.pos())` at startup.
14. ✅ **Stale screen geometry on resolution change** — `screen.geometryChanged` + `availableGeometryChanged` connected to `_on_screen_changed`.
15. ✅ **Dead-pipe guard on send** — `is_alive()` check before write; emits `session_died` on dead pipe or write failure.
16. ⏳ **Auto-reconnect on EOF** — *partial:* `session_died` shown to chat + tray tooltip flips to "session ended"; user must click **Restart Claude**. No auto-retry/backoff yet.
17. ✅ **Output buffer cap** — `setMaximumBlockCount(5000)`.
18. ✅ **Bubble debounce** — `BUBBLE_DEBOUNCE_MS=400` via `QElapsedTimer`.
19. ✅ **Crash recovery** — `_install_excepthook()` → `~/.agentrocky/log.txt` + `QMessageBox.critical` dialog.
20. ⏳ **Locale / encoding sanity** — `utf-8 errors=replace` confirmed; `PYTHONIOENCODING=utf-8` env override **not** added. Low priority; revisit if non-ASCII issues seen.

### Performance
21. ✅ **Pre-flip walk pixmaps once** — `_load_sprites` caches `key + "_r"` variants.
22. ⏳ **Lower walk fps to 30** — *skipped:* kept 8fps walk-cycle (matches original feel). Move timer still 60fps.
23. ✅ **High-DPI scaling** — `SPRITE_SIZE * devicePixelRatio()` + `setDevicePixelRatio(dpr)`. Sprites pull DPR at load time from screen-under-cursor.
24. ✅ **Stop move timer when chat open** — `move_timer.stop()` + `walk_timer.stop()` on open, restart on close.

### Safety / privacy
25. ✅ **Per-session opt-in (not persistent)** — confirmed design. Dialog re-shows each launch; no "remember me".
26. ✅ **Audit log** — `audit("user_send"|"tool_use", payload)` to `~/.agentrocky/audit.log`. No assistant text or results.
27. ✅ **Restrict cwd to workspace folder** — `WORKSPACE = ~/agentrocky-workspace`, auto-created, overridable via `AGENTROCKY_CWD` env.
28. ✅ **Token / cost counter in chat header** — `usage_updated` signal accumulates `input + output + cache_read + cache_creation` into header label.
29. ✅ **First-run dialog: stronger warning** — concrete bullet list incl. workspace path + audit path.
30. ✅ **Idle screen-lock detection** — `OpenInputDesktop` poll every 3s; hides rocky+bubble+chat on lock, restores prior visibility on unlock.

### Behavior parity
31. ⏳ **Bubble fires per `tool_use` block** — open. Current spams; debounce (#18) softens but doesn't fully match upstream. Need to diff Swift to confirm.
32. ⏳ **Direction snap on chat-open** — open. Sprite freezes mid-step on `stand`; upstream behavior unverified.
33. ⏳ **Walk speed tuning** — open. Currently 1.5px/tick (~90px/s). No upstream constant captured.

### Distribution (later)
34. ⏳ **PyInstaller single-exe** — deferred until after demo recording.
35. ⏳ **Optional autostart** — deferred. Registry toggle in tray menu.

---

## Priority groupings

### P0 — shipped ✅
- 1: tray icon + Quit menu
- 3: kill subprocess on quit
- 4: single-instance lock
- 5: drop `[claude ready]`
- 26: audit log — **sends + tool_use only** (no assistant text, no results)
- 27: switch cwd to `~/agentrocky-workspace` (auto-create if missing)

### P1 — shipped ✅ (with caveats)
- 9: streaming cursor ✅
- 10: cwd label in prompt ❌ reverted
- 13/14: multi-monitor ✅
- 15: dead-pipe guard ✅
- 16: auto-reconnect ⏳ partial (manual restart only)
- 17: output buffer cap ✅
- 29: stronger first-run warning ✅

### P2 — shipped ✅
- 2: right-click context menu
- 6/7/8: Esc / Ctrl+L / history
- 11: bubble wrap
- 12: pause idle on chat open
- 18: bubble debounce
- 21/24: pixmap cache + timer pause
- 28: token counter

### P3 — partial
- 19: crash log ✅
- 23: high-DPI ✅
- 30: lock-screen hide ✅
- 34/35: PyInstaller, autostart ⏳ deferred (post-demo)

### Open / not scheduled
- 16: auto-reconnect with backoff
- 20: `PYTHONIOENCODING=utf-8` env defensive
- 22: lower walk fps (skipped — kept 8fps)
- 31/32/33: behavior-parity nits vs. Swift original

---

## Files modified
- `rocky.py` only.

## New runtime artifacts
- `~/.agentrocky/audit.log` (P0)
- `~/.agentrocky/log.txt` (P3)
- `~/agentrocky-workspace/` (P1, auto-created)

## P0 implementation sketch

### imports added
`QSystemTrayIcon`, `QMenu`, `QAction` from QtWidgets/Gui; `QSharedMemory` from QtCore; `datetime` stdlib.

### single-instance
Top of `main()` before QApplication construction is fine, but `QSharedMemory` needs QApp first. Order:
```python
app = QApplication(sys.argv)
shm = QSharedMemory("agentrocky-singleton-v1")
if not shm.create(1):
    return 0   # silent exit
app._shm = shm  # keep ref alive
```

### workspace cwd
```python
WORKSPACE = Path.home() / "agentrocky-workspace"
WORKSPACE.mkdir(exist_ok=True)
# in ClaudeSession.start: cwd=str(WORKSPACE) instead of Path.home()
```

### kill subprocess on quit
Add `ClaudeSession.stop()`:
```python
def stop(self):
    if not self.proc: return
    try: self.proc.stdin.close()
    except Exception: pass
    try:
        self.proc.terminate()
        self.proc.wait(timeout=2)
    except Exception:
        try: self.proc.kill()
        except Exception: pass
```
Wire: `app.aboutToQuit.connect(session.stop)`.

### tray icon
```python
tray = QSystemTrayIcon(QIcon(str(SPRITE_DIR / "stand.png")), app)
menu = QMenu()
menu.addAction("Show Chat", rocky._toggle_chat_force_show)
menu.addAction("Hide Rocky", rocky.hide)
menu.addAction("Show Rocky", rocky.show)
menu.addSeparator()
menu.addAction("Quit", app.quit)
tray.setContextMenu(menu)
tray.show()
app._tray = tray
```

### drop [claude ready]
Remove L444-445 `session.ready.connect(lambda: ...)`. Add `_session_ready` bool on ChatWindow flipped by ready signal; gate first send so user sees no line but can't fire prematurely. Optional: tray tooltip "Rocky (ready)" / "Rocky (starting…)".

### audit log
```python
AUDIT = Path.home() / ".agentrocky" / "audit.log"
AUDIT.parent.mkdir(exist_ok=True)
def audit(kind: str, payload):
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.utcnow().isoformat(),
                            "kind": kind, "data": payload}) + "\n")
```
Hook in `ClaudeSession.send` (kind="user_send") and `_dispatch` tool_use branch (kind="tool_use", payload includes name + input).

## Verification (P0)
1. `pythonw rocky.py` → tray icon shows; rocky walks
2. Right-click tray → Quit → both pythonw.exe and claude.exe gone (Task Manager)
3. Second `pythonw rocky.py` → exits immediately, only one rocky
4. First message → no `[claude ready]` line; warning dialog still appears
5. After tool-using turn: `cat ~/.agentrocky/audit.log` → 2+ JSON lines (user_send, tool_use)
6. `ls ~/agentrocky-workspace` → exists; ask claude to write a file → lands there, not in `~`
