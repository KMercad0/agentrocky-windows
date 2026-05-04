# QoL + Performance Improvements

Triage notes for `rocky.py` ahead of distribution. Items marked **[shipped]** landed in the
quick-wins pass; the rest are backlog.

## Performance

1. **[shipped] Halve idle CPU** — `MOVE_TICK_MS` 16→33 (60→30 fps), `WALK_SPEED_PX` 1.5→3.0
   to preserve ~90 px/s. Walk-frame timer at 8 fps unchanged.
2. **[shipped] Buffered audit writer** — `audit()` now appends to an
   in-memory list under `threading.Lock`; a 1 s `QTimer` flushes to disk in
   one `open/write/close` cycle, with a final flush on `aboutToQuit`. Reader
   threads no longer open files on the hot path.
3. **[shipped] Batched HTML append** — `ChatWindow.append_line` queues
   `<div>`-wrapped lines and flushes via single `QTextCursor.insertHtml` on a
   50 ms one-shot timer. Ctrl+L drops the pending buffer.
4. **[shipped] Autoscroll yank** — guard `moveCursor(End)` so user mid-scroll isn't
   yanked back to the bottom.
5. **[shipped] Audit log unbounded** — rotate `audit.log` and `log.txt` at 5 MB
   (single `.1` generation, ≤10 MB total).
6. **[shipped] `HistoryLineEdit._history` unbounded** — cap 500 entries, FIFO trim in `push()`.
7. **[shipped] Sprite DPI reload on monitor switch** — `_on_screen_changed`
   re-runs `_load_sprites()` whenever the active screen's DPR differs from the
   cached `_sprite_dpr`. Sprites stay crisp across mixed-DPI monitors.
8. **[shipped] `QFileSystemWatcher` dir change skips unrelated writes** —
   `ReminderManager` and `HealthCheckManager` split file-vs-dir handlers; dir
   handler short-circuits unless the watched JSON's `mtime_ns` actually moved.
9. **[shipped] Event-driven lock detection** — `Rocky` registers for
   `WM_WTSSESSION_CHANGE` via `WTSRegisterSessionNotification` in `showEvent`,
   handles LOCK/UNLOCK in `nativeEvent`, and unregisters in `closeEvent`. The
   3 s polling timer is gone; idle wakeups drop further.
10. **[shipped] PyInstaller `--onefile` slow startup** — every launch extracts to
    temp. Switch to `--onedir`; cold start ~3-5× faster.

## Quality of life

11. **[shipped] AppUserModelID** — set
    `SetCurrentProcessExplicitAppUserModelID("agentrocky.app")` so toasts and
    taskbar group under "agentrocky" instead of "python.exe".
12. **[shipped] Excepthook now marshals dialog to GUI thread** —
    `QTimer.singleShot(0, ...)` posts the `QMessageBox.critical` to the main
    event loop. Reader-thread crashes no longer call Qt UI from a worker.
13. **[shipped] Multi-line chat input** — `HistoryLineEdit` is now a
    `QPlainTextEdit` subclass. Enter submits, Shift+Enter inserts a newline,
    Up/Down navigate history when the cursor is on the first/last block. The
    box auto-grows up to `MAX_LINES`, then scrolls.
14. **[shipped] Restart Claude leaves stale usage counter** — reset
    `ClaudeSession._usage_total` and re-emit on restart.
15. **[shipped] Global hotkey Ctrl+Alt+R** — `GlobalHotkey` registers via
    Win32 `RegisterHotKey` and dispatches via a `QAbstractNativeEventFilter`
    on the `QApplication`. Triggers `Rocky.show_chat`. `MOD_NOREPEAT` set so
    held keys don't spam.
16. **[shipped] `show_toast` caches notifier + classes** — first call loads
    winrt, stashes `ToastNotification`/`XmlDocument` and the notifier instance
    in module-level globals. Subsequent calls reuse them; persistent failure
    flips a disabled flag.
17. **[shipped] WAV durations parsed lazily** — `VoicePack._duration_ms` opens
    the wave file only on first `play()` per clip and memoises the result.
18. **[shipped] Reminder timer chaining** — `_arm_timer` clamps to
    `TIMER_MAX_MS` (int32 limit); `_on_timer_due` re-arms when residual delta
    is still in the future. Reminders >24 days fire on the correct day.
19. **[shipped] Tray "Open Crash Log" entry** — mirrors "Open Audit Log",
    no-op if `log.txt` doesn't exist yet.
20. **[shipped] First-run sprite-missing dialog** — now creates the
    `sprites/` folder if absent and offers an "Open Sprite Folder" button so
    the user can drop the PNGs straight in.
21. **[shipped] "Pause Walk" toggle** — checkable tray item + right-click
    menu entry. Stops move/walk/idle/jazz timers, snaps to stand sprite. Honoured
    by chat-close and health-ack resume paths so motion stays paused until
    explicitly unchecked. Session-only state.

## Build / packaging

22. **[shipped] `--onedir` build** (see #10).
23. **Sign the exe**. Unsigned binaries trip SmartScreen on download. Either get a
    code-signing cert or document the SmartScreen warning in the README.
24. **[shipped] README build/packaging section** — onedir layout, MCP sidecar
    placement, SmartScreen warning, global hotkey, and updated tray menu
    entries are documented.

## Notes

- Behaviour-parity constants near the top of `rocky.py` (`WALK_SPEED_PX`,
  `JAZZ_DURATION_MS`, etc.) match the upstream Swift app. The 30 fps move tick in
  item #1 keeps the visible speed identical; only the wake frequency changes.
- Voice clips are CC-BY-NC-4.0 (`sounds/LICENSE-VOICE.md`). Non-commercial
  distribution only.
- Sprite assets are not in this repo and must not be committed.
