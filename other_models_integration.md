# Other Models Integration (parked)

Future work. Not part of the .exe packaging milestone. Default backend stays
`claude` (Anthropic CLI). Goal: add a free-tier alternative so users without a
Claude subscription can run Rocky.

## Decision

**Path 1 — Gemini CLI** (`@google/gemini-cli`).

- Free tier: ~60 rpm / 1000 rpd via personal Google account.
- Supports MCP, so `mcp_server.py` and the four `rocky.*` tools port over
  unchanged.
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
