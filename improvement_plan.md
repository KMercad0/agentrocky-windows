# Plan: agentrocky Windows port — improvements

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
1. **System tray icon + Quit menu** — `QSystemTrayIcon` (using `stand.png` as icon), right-click menu: Show Chat / Hide Rocky / Restart Claude / Quit. Removes Task Manager dependency.
2. **Right-click rocky → context menu** — same actions inline. Faster than tray.
3. **Kill subprocess on quit** — `app.aboutToQuit.connect(session.stop)` → `proc.stdin.close()` + `proc.terminate()` + `wait(2s)` + `kill()` fallback. Currently orphans `claude.exe`.
4. **Single-instance lock** — `QSharedMemory` key `"agentrocky-singleton"`. Second launch detects, exits silently (or focuses existing rocky via show/raise). Prevents 2× API costs, overlapping sprites.

### Cosmetic / UX
5. **Drop `[claude ready]` line** (L444-445) — keep `ready` signal internally as `_session_ready` flag, gate first send. Don't print.
6. **Esc closes chat** — `keyPressEvent` on ChatWindow.
7. **Ctrl+L clears terminal** — `output.clear()`.
8. **Up/Down arrow history** — `list[str]` of sent messages, index navigation in input.
9. **Streaming `▋` cursor while running** — show during `isRunning` (between user send and `result` msg). Match original.
10. **cwd basename in prompt label** — `Path.home().name + " ❯ "` instead of just `❯`. Match original.
11. **Bubble word-wrap + max width** — cap bubble width (e.g., 280px), wrap text.
12. **Pause idle jazz timer when chat open** — currently fires no-op but still wakes process.

### Robustness
13. **Multi-monitor awareness** — use screen under cursor at startup; recompute geometry on `screenChanged` / `geometryChanged`. Currently hard-pinned to primary.
14. **Stale screen geometry on resolution change** — same fix as #13.
15. **Dead-pipe guard on send** — `proc.poll()` check before write; surface "session ended" to chat if dead.
16. **Auto-reconnect on EOF** — detect stdout close, show error + Restart button (or auto-restart once with backoff).
17. **Output buffer cap** — `output.document().setMaximumBlockCount(5000)`. Prevents RAM bloat over long sessions.
18. **Bubble debounce** — ignore new bubble if current shown <500ms ago, OR queue. Prevents flicker on tool_use spam.
19. **Crash recovery** — `sys.excepthook` → log to `~/.agentrocky/log.txt` + show error dialog before exit.
20. **Locale / encoding sanity** — already `utf-8` errors=replace. Verify with non-ASCII prompt; add `PYTHONIOENCODING=utf-8` to subprocess env defensively.

### Performance
21. **Pre-flip walk pixmaps once** — cache `walk1_right`, `walk2_right` etc. Stops `transformed()` allocation each 8fps tick (L492).
22. **Lower walk fps to 30** — eye won't notice; halves wakeups. Optional.
23. **High-DPI scaling** — render sprites at `SPRITE_SIZE * devicePixelRatio()`, set `setDevicePixelRatio` on pixmap. Currently soft on 4K @ 200%.
24. **Stop move timer when chat open** (currently no-ops but wakes) — `move_timer.stop()` on chat open, `start()` on close. Same for walk_timer.

### Safety / privacy
25. **Per-session opt-in persistence opt-out** — keep current per-launch dialog (NOT persistent). Persistent opt-in trades safety for clicks; not worth.
26. **Audit log** — append every `send()` payload + every `tool_use` JSON to `~/.agentrocky/audit.log` with timestamp. Forensics if claude trashes files.
27. **Restrict cwd to workspace folder** — `~/agentrocky-workspace` (auto-create). Limits blast radius vs. full `~`. Make configurable via env var `AGENTROCKY_CWD`.
28. **Token / cost counter in chat header** — parse `usage` from `result` messages, accumulate, show running total. Surfaces API spend.
29. **First-run dialog: stronger warning** — list concrete examples ("can read SSH keys", "can run `rm`", "talks to api.anthropic.com"). Current dialog vague.
30. **Idle screen-lock detection** — Win32 `WTSQuerySessionInformation` or simpler: hide chat on session lock. Prevents walk-up attack on unlocked-then-locked PC.

### Behavior parity
31. **Bubble fires per `tool_use` block** — original may fire once per turn. Confirm vs. upstream Swift; current spams on multi-tool turns.
32. **Direction snap on chat-open** — original may force facing left/right. Current freezes mid-step.
33. **Walk speed tuning** — 1.5px/tick = 90px/s. Original constant unknown. Test feel; consider 2.0-2.5.

### Distribution (later)
34. **PyInstaller single-exe** — `pyinstaller --noconsole --add-data "sprites;sprites" rocky.py`. Handle `sys._MEIPASS` path for sprites.
35. **Optional autostart** — registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` toggle in tray menu.

---

## Priority groupings

### P0 — selected by user (this PR)
- 1: tray icon + Quit menu
- 3: kill subprocess on quit
- 4: single-instance lock
- 5: drop `[claude ready]`
- 26: audit log — **sends + tool_use only** (no assistant text, no results)
- 27: switch cwd to `~/agentrocky-workspace` (auto-create if missing)

### P1 — robustness + parity
- 9: streaming cursor
- 10: cwd label in prompt
- 13/14: multi-monitor
- 15: dead-pipe guard
- 16: auto-reconnect
- 17: output buffer cap
- 27: cwd workspace
- 29: stronger first-run warning

### P2 — UX polish
- 2: right-click context menu
- 6/7/8: Esc / Ctrl+L / history
- 11: bubble wrap
- 12: pause idle on chat open
- 18: bubble debounce
- 21/24: pixmap cache + timer pause
- 28: token counter

### P3 — distribution / advanced
- 19: crash log
- 23: high-DPI
- 30: lock-screen hide
- 34/35: PyInstaller, autostart

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
