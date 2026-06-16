# Plan: Rocky 1-Stop-Shop Install

Goal: a non-technical Windows user double-clicks **one `RockySetup.exe`**, gets a
first-run screen with three buttons — **Claude / Gemini (free) / None** — and ends
up with a working Rocky. No manual Python. No manual Node. No manual npm. No
manual sprite copy.

---

## ⏩ STATUS UPDATE (2026-06-16) — what actually shipped (supersedes the phased plan below)

Karl revised several locked decisions. The installer now produces a **working,
walk-out-of-the-box Rocky from one `RockySetup.exe`**. Current reality:

- **Phase 1 (one Setup.exe): DONE + rebuilt.** `installer\Output\RockySetup.exe`
  (~53 MB) rebuilt 2026-06-16 with the current code. Installs per-user (no UAC),
  Start Menu + optional desktop/startup shortcuts.
- **Sprites: BUNDLED, not auto-downloaded.** Karl chose to bundle the 6 PNGs into
  the installer (accepting the redistribution/takedown risk himself). `rocky.iss`
  ships `..\sprites\*` → `{app}\sprites`; **Phase 2 (auto-download) is dropped.**
- **App + installer icon: DONE.** `rocky.spec` generates `app.ico` from
  `sprites\stand.png` at build time (cropped/squared); `rocky.exe`, the installer,
  and shortcuts all show Rocky. `app.ico` is gitignored (sprite derivative).
- **The Claude security HIGH: FIXED.** Claude is now **safe-by-default**
  (`--tools "" --allowedTools "mcp__agentrocky__*"` — MCP tools only, no shell/file
  access) with `--dangerously-skip-permissions` as a tray opt-in behind a warning,
  plus `--strict-mcp-config` to block the user's other MCP servers leaking in.
  This replaces the "two build profiles" idea — it's one build, runtime toggle.
- **Phase 3 (first-run backend wizard): DROPPED.** Decision: the single-`.exe`
  priority is *Rocky runs immediately*. Default backend is **None** (walks, no AI,
  no cost). Claude/Gemini are **optional, manual, and guided** (tray Backend menu +
  docs), not wired into the installer. More clicks for AI is acceptable.
- **Phase 4 (bundle portable Node for Gemini): DROPPED.** Gemini stays manual like
  Claude — the user installs Node + `@google/gemini-cli` themselves; we just
  document it (README Backends, How-to-Run "Adding an AI backend").
- **Phase 5 (Gemini MCP): still deferred** (unchanged).

**Remaining before a public release:** (1) actually test-install `RockySetup.exe`
on a clean machine/VM (only ever compiled + locally built, never clean-installed);
(2) code signing still absent → SmartScreen "More info → Run anyway" documented;
(3) sprite license remains the legal risk Karl has accepted.

The phased plan below is kept for history; where it conflicts with this section,
this section wins.

---

Status (2026-05-30, historical): decisions locked. **Phase 1 done + compiles** —
`installer\Output\RockySetup.exe` (49.3 MB) built via ISCC 6.7.3. Phases 2–5
pending. Phase 1 alone does **not** yield a working app (needs Phase 2 sprites —
see ordering warning below).

---

## Why this is needed

The current install is too heavy for non-technical users.

### Path A — from source (`setup.bat`): 7 steps, 3 installers
1. Install Python 3.10+ manually (must tick "Add to PATH" — easy to miss, breaks all).
2. `setup.bat` → venv + `pip install` PyQt6 + mcp + winrt.
3. Install Node.js manually.
4. `npm install -g @anthropic-ai/claude-code`.
5. `claude login`.
6. Copy 6 sprite PNGs from upstream repo into `./sprites/`.
7. `pythonw rocky.py`.

### Path B — frozen build (`dist/`)
PyInstaller **onedir** already ships: `dist/rocky/rocky.exe` +
`dist/mcp_server.exe` (~65MB zip).
- ✅ Python already eliminated (frozen exe carries its own).
- ❌ Still needs Node + npm for the CLI.
- ❌ Still needs sprites copied.
- ❌ It's a folder, not one artifact.

### Real blockers (only three)
| Blocker | Status |
|---|---|
| Python runtime | ✅ solved by frozen exe |
| LLM CLI (Node/npm) | ⚠️ the big one — see keystone below |
| Sprites not bundled (license) | ❌ open |

---

## Keystone finding (verified against official docs, 2026-05)

- **Claude Code now has a native Windows installer — GA, needs NO Node.js:**
  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```
  Downloads a binary into `~/.local/bin`, sets PATH, self-updates. Anthropic's
  recommended default method.
- **Gemini CLI still requires Node.js 20+** (npm / npx / conda only; no
  standalone Windows binary, no winget, no scoop).

→ The *default* (Claude) path can be near-frictionless with zero Node. The *free*
(Gemini) path is the only thing that still drags in Node — so we bundle our own
Node just for it.

---

## How comparable apps do "1-stop"

Reframe: **nobody ships one bare `.exe`** for an app this size. "1-stop" = one
**`Setup.exe`** that **bundles its own runtimes** instead of asking the user to
install them.

| App | Installer | Runtime strategy |
|---|---|---|
| Ollama | single Setup.exe | bundles runtime, models on first use |
| VS Code | Inno Setup | bundles Electron/Node |
| Discord / Slack | Squirrel.Windows | bundle Node, auto-update |
| Cursor / AI desktop apps | NSIS / Squirrel | bundle Node, models via API |

Lessons applied:
1. "1-stop" = one `Setup.exe`, not one bare exe. (Avoid PyInstaller `--onefile`:
   slow cold start + frequent antivirus false-positives.)
2. Node-dependent apps never ask the user to install Node — they ship a private
   copy.

---

## Locked decisions (2026-05-30)

| Decision | Choice |
|---|---|
| Gemini's Node dependency | **Bundle portable Node 20** + pre-installed `@google/gemini-cli` inside Rocky's app dir (~+80–120MB). True 1-click for Gemini. |
| Sprites | **Auto-download on first run** from upstream GitHub, with a credit notice. Fetch on the user's behalf, never redistribute. |
| Packaging | **Inno Setup → one `RockySetup.exe`.** Onedir payload inside, Start Menu + desktop shortcut, autostart toggle. Fast startup. |
| First step | Write this plan doc (done), then build the phases below. |

---

## Build phases

> **⚠️ Phase ordering — Phase 1 is NOT independently shippable.**
> The installer excludes sprites (license). `main()` (`rocky.py:2397-2421`) checks
> `SPRITE_FILES` and, on any missing file, shows a `QMessageBox.critical`
> ("Missing sprite files in ./sprites/") then `return 1`. **No graceful degrade.**
> So a fresh install on a clean machine → launch → "missing sprites" dialog →
> exit. **Phase 1 only yields a working app once Phase 2 (sprite auto-download)
> lands.** Ship them together, or do Phase 2 first.

### Phase 1 — Package into one Setup.exe (kills Python, makes it one artifact) — ✅ DONE (compiles)
- Keep the existing PyInstaller onedir builds for `rocky` + `mcp_server`.
- **Done:** `installer/rocky.iss` (Inno Setup) + `installer/build_installer.bat`
  (one-shot build chain). Details:
  - Bundles all of `dist/rocky/` (`rocky.exe` + `_internal/` + `mcp_server.exe`).
    `sounds/` already lives inside `_internal/` (PyInstaller `datas`) — not shipped
    separately.
  - **Sprites excluded** from the payload (license) → fetched at first run (Phase 2).
  - Installs to `%LOCALAPPDATA%\Rocky` via `PrivilegesRequired=lowest` → no
    admin/UAC prompt.
  - Start Menu shortcut always; **desktop shortcut** + **"start at login"** as
    optional checkboxes (`[Tasks]`). The startup task drops a shortcut in
    `{userstartup}` (independent of tray autostart item #35; the two can converge
    later).
  - `[UninstallDelete]` removes runtime-downloaded `sprites\`; user data under
    `~/.agentrocky\` + workspace left intact on purpose.
- **Build:** `installer\build_installer.bat` from repo root → PyInstaller both
  exes → stage sidecar → compile → `installer\Output\RockySetup.exe`.
  Needs Inno Setup 6 (`winget install JRSoftware.InnoSetup`).
- **Phase 1 gap — no app icon.** `rocky.spec` sets no `icon=`, so `rocky.exe`,
  the installer, and shortcuts all show the generic Windows exe icon — looks
  untrustworthy to exactly the non-technical users this targets. Fix: add a
  `rocky.ico`, set `icon=` in `rocky.spec` and `SetupIconFile` in `rocky.iss`.
- **✅ Compiled:** `ISCC 6.7.3` on the existing `dist\rocky\` → `RockySetup.exe`
  (49.3 MB), 2026-05-30. Inno is at
  `~\AppData\Local\Programs\Inno Setup 6\ISCC.exe`. Compile log confirms the
  payload includes `_internal\sounds\*` and `winrt` bindings, and **no sprite
  files** (correctly excluded).
- **Still unverified — actual install behavior.** Compiling ≠ a working install.
  Not yet run: double-click `RockySetup.exe` → does it install to
  `%LOCALAPPDATA%\Rocky` with no UAC, drop shortcuts, and launch? That's the next
  check (blocked on Phase 2 for a *fully* working run, but the install mechanics
  can be tested independently).
- **Verified against the built `dist\rocky\`:** `sounds/` ships inside
  `_internal/sounds/` (no separate copy needed). Current `dist\rocky\` has no
  `sprites\` subdir (the dev PNGs live in top-level `dist\sprites\`), but
  `build_installer.bat` still hard-deletes `dist\rocky\sprites\` if a build ever
  stages one there — belt-and-suspenders with the `.iss` `Excludes`.
- **Verify (pending):** fresh Windows VM, no Python/Node → double-click
  `RockySetup.exe` → install → Rocky walks. None-backend chat shows the canned
  reply.

### Phase 2 — Sprites auto-download on first run
- On launch, if `SPRITE_FILES` missing from the external sprite dir
  (`external_path()`), show a one-time dialog: "Rocky needs his sprites (from the
  original project by @itmesneha). Download now?" + upstream credit + link.
- Fetch the six PNGs from upstream into the external sprite dir, then continue
  startup.
- Handle offline / fetch-fail gracefully: clear message + retry, don't crash.
  Fall back to a manual "open sprites folder + open upstream repo" path (today's
  `setup.bat` behavior) if download is declined or blocked.
- **Verify:** delete sprites → launch → accept → sprites land → Rocky walks.
  Relaunch → no re-download. Decline → graceful manual fallback.

### Phase 3 — First-run backend wizard (the actual ask)
Provider plumbing already exists (`AgentSession` strategies, tray Backend menu,
`settings.json`). This phase wires an installer-grade first-run UI to it.

First run shows **[Claude] [Gemini (free)] [None]**:
- **None** → write `settings.json` provider=none. Instant, zero deps.
- **Claude** → run `irm https://claude.ai/install.ps1 | iex` in-process (no Node),
  show progress, then trigger `claude login` (browser/device flow). On success set
  provider=claude.
- **Gemini (free)** → point `GeminiStrategy` at the **bundled portable Node**
  (Phase 4); no system Node needed. Run Gemini's Google-account auth (device
  flow). Set provider=gemini.
- Re-runnable later from the tray Backend menu (already exists).
- **Verify (per backend):** pick it → it installs/auths with no terminal → send a
  message → real model reply (or canned reply for None).

### Phase 4 — Bundle portable Node for Gemini
- Vendor a portable Node 20+ runtime into the installer payload
  (`installer/node/`); pre-install `@google/gemini-cli` against it at build time.
- `GeminiStrategy` resolves its `gemini` via the bundled Node first, system
  `gemini` as fallback (mirror `_locate_claude_cli` pattern).
- **Verify:** on a VM with no system Node, pick Gemini → runs purely off the
  bundled runtime.

### Phase 5 — Wire Gemini MCP (carried from `other_models_integration.md`)
Out of scope for the installer itself, but the natural follow-on: the four
`rocky.*` tools are Claude-only today. Wire Gemini CLI's MCP config so reminders /
notes / health-via-chat work on the free backend too.

---

## Open risks / watch-items
- **⚠️ Sprite license is the real legal risk.** Upstream
  [itmesneha/agentrocky](https://github.com/itmesneha/agentrocky) has **no LICENSE
  file** → the art is default "all rights reserved." Auto-download (fetch for the
  user, never redistribute, never commit) is the *least-bad* option, but it is not
  airtight. Safest long-term fix: ask @itmesneha for explicit redistribution
  permission, or commission original sprites we own. Keep the credit visible and
  never bundle sprites into the installer.
- **Claude native installer** — was beta, now GA, but pin/verify it and re-test
  when it moves. Have a fallback message if `install.ps1` fails.
- **Antivirus / SmartScreen** on an unsigned `Setup.exe` — consider code signing,
  or document the "More info → Run anyway" step (already in How-to).
- **Installer size** — bundled Node pushes the download to ~150–200MB. Acceptable
  per Ollama / VS Code precedent, but note it.
- **Gemini CLI stream-schema drift** — already flagged; pinning the bundled
  version reduces breakage. Gemini path is still untested against a live CLI (see
  `other_models_integration.md`).
- **⚠️ Claude backend runs with auto-approved tools — unsafe default for non-tech
  users.** Claude launches with `--dangerously-skip-permissions` AND the full default
  toolset, so the workspace is NOT a sandbox — it can run shell commands and touch any
  file the user's account can. Fine for the dev/power-user build (honestly disclosed in
  the opt-in dialog), but a liability when shipped to non-technical users who can't weigh
  that dialog. Fix for the installer build (verified `--allowedTools`/`--disallowedTools`/
  `--tools` exist in the CLI): ship **two profiles** — installer build restricts Claude
  to only the `rocky.*` MCP tools (no Bash/Write → kills the prompt-injection→RCE path);
  dev build keeps the full toolset + opt-in. Not yet built. Free hardenings already
  shipped (honest dialog copy + anti-injection persona rule, commit `1546350`).
  **Gemini is already safe:** switched from `--approval-mode yolo` to `--approval-mode
  plan` (read-only) — chat + file reads only, no commands/writes. Its opt-in dialog is
  now an informational notice, not a risk warning. So this HIGH applies to **Claude
  only**.

---

## Success criteria (the whole point)
Fresh Windows machine, no Python, no Node:
1. Double-click `RockySetup.exe` → next → finish.
2. Rocky walks; sprites auto-downloaded.
3. First-run screen → pick Claude / Gemini / None.
4. Chosen backend installs + authenticates with no terminal, no npm.
5. Send a message → real reply.

If a non-technical user can do all five without help, the goal is met.
