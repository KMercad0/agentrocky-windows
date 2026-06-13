# Other Models Integration

Goal: let users without a Claude subscription run Rocky.

## Status (shipped)

The provider abstraction is in, and **all three backends now run**. Each
`_ProviderStrategy` owns its own process lifecycle and stream parsing; the host
(`AgentSession`) just forwards `start`/`send`/`stop` and aggregates usage. Chosen
from the tray "Backend" submenu, persisted to `~/.agentrocky/settings.json`:

- **none** — standalone walker + health check-ins, no LLM. First-launch default
  when `claude` is not on PATH (auto-detected by `load_provider`).
- **claude** — `ClaudeStrategy`: one persistent stream-json subprocess (stdin
  per turn) + MCP tools + skip-permissions opt-in dialog.
- **gemini** — `GeminiStrategy`: **live** via the Gemini CLI (Path 1 below).

Switching is `AgentSession.set_provider()` → stop → swap strategy → start; the
signal contract is constant so `Rocky` never re-wires.

### How Gemini runs (shipped)

Unlike Claude's persistent stdin stream, the Gemini CLI runs **one-shot per
turn**, so `GeminiStrategy.send()` spawns a fresh process each turn:

```
gemini --output-format stream-json --skip-trust --approval-mode yolo [--resume latest] -p PROMPT
```

- `--resume latest` carries conversation state across turns (omitted on the
  first turn — `_first` flips to `False` only after a turn that produced a
  `result`, so a failed first turn doesn't poison turn 2).
- `--approval-mode yolo` is the Gemini equivalent of
  `--dangerously-skip-permissions`, so the opt-in warning dialog fires for it
  too (`supports_dangerous_opt_in = True`).
- Stream schema differs from Claude — parsed in `GeminiStrategy._run`:
  `{type:"message", role:"assistant", content, delta}` (delta chunks
  accumulated, flushed on a non-delta message / tool / result),
  `{type:"tool_use", tool_name}`, `{type:"result"}` (no `usage`, so the token
  counter shows `0`).
- stderr is drained on a side thread (avoids pipe deadlock) and surfaced as an
  `error` line only when the turn fails (nonzero exit with no `result`).

**Known limitation — no MCP for Gemini (V1).** The four `rocky.*` tools
(reminders / notes / health-via-chat) are **Claude-only** for now. Gemini runs
with no `--mcp-config`; wiring the Gemini CLI MCP path is the next step.

**Untested against the live CLI.** The flags/schema above match the
[sa7v1x3n fork](https://github.com/sa7v1x3n/agentrocky-windows) (empirical) and
are covered by a synthetic-stream parser test, but no one has run this against
an installed `gemini` yet. To verify: `npm i -g @google/gemini-cli`, run
`gemini` once to authenticate, then pick **Backend ▸ Gemini** in the tray.

## Path 1 — Gemini CLI (chosen)

`@google/gemini-cli`.

- Free tier: ~60 rpm / 1000 rpd via personal Google account.
- Supports MCP (not yet wired here — see limitation above).
- Closest swap to current architecture (CLI subprocess + stdio).

## Sketch

- Rename `ClaudeSession` → `AgentSession`. Strategy object holds: CLI binary,
  argv shape, stream parser.
- Add `--provider {claude,gemini}` flag (or env `AGENTROCKY_PROVIDER`).
- Per-provider stream parser:
  - claude → current stream-json
  - gemini → adapter (Gemini CLI output format differs)
- Per-provider MCP wiring: confirm Gemini CLI MCP config path / syntax. Keep
  `mcp_server.py` unchanged.
- Tray menu: provider toggle + "active provider" tooltip.
- README: new "Free option: Gemini CLI" section with `npm i -g @google/gemini-cli`
  + auth steps.

## Risks

- Gemini CLI stream format moves frequently — adapter may break across versions.
- Tool-call semantics differ across providers; bubble debounce may need
  per-provider tuning.
- Free-tier rate limits will hit heavy-tool turns harder than Claude does.
- MCP support in Gemini CLI is newer; verify the four `rocky.*` tools dispatch
  correctly before committing to the path.

## Rejected for now

- **Ollama / local model** — fully free, no key, no quota, offline. But MCP
  support across local models is unreliable; would force reimplementing tool
  dispatch inside `rocky.py`. Worth revisiting once the `AgentSession`
  abstraction exists — drop-in as a third provider.
- **Direct API SDK** (Groq / Gemini / DeepSeek SDK) — most control, most code.
  Loses the "talks to a real coding agent" feel; becomes a chat client. Skip
  unless we want a multi-provider switcher later.

## Prerequisites before starting

1. `.exe` packaging milestone shipped + stable.
2. Provider abstraction designed (rename + strategy pattern) — touches
   `ClaudeSession` (rocky.py l. 294) and the spawn wiring in `_write_mcp_config`
   (rocky.py l. 94).
3. Confirm current Gemini CLI MCP config syntax against upstream docs.
