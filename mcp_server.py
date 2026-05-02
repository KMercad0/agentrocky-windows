"""
agentrocky MCP server — exposes typed tools to Claude:

  rocky.reminder    one-shot toast on a future timestamp / duration
  rocky.note        append timestamped line to notes file
  rocky.open        open URL in default browser, or file inside workspace
  rocky.launch_app  spawn whitelisted desktop apps (notepad, word, etc.)

Spawned by rocky.py as a stdio sidecar via --mcp-config. Side effects land in
~/.agentrocky/ and the workspace; rocky.py picks up reminder writes via
QFileSystemWatcher and schedules QTimer fires.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


# -- paths (must match rocky.py) ---------------------------------------------

WORKSPACE = Path(os.environ.get("AGENTROCKY_CWD") or (Path.home() / "agentrocky-workspace"))
AUDIT_DIR = Path.home() / ".agentrocky"
AUDIT_LOG = AUDIT_DIR / "audit.log"
REMINDERS_JSON = AUDIT_DIR / "reminders.json"
HEALTH_JSON = AUDIT_DIR / "health.json"
NOTES_FILE = WORKSPACE / "notes.md"

# Mirror rocky.py HEALTH_DEFAULT_CATS keys; tool only allows mutating these.
HEALTH_CATS = ("water", "stretch", "eyes", "posture", "mental")

WORKSPACE.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


# -- whitelists / parsers -----------------------------------------------------

LAUNCH_WHITELIST = {
    "notepad":     "notepad.exe",
    "calc":        "calc.exe",
    "calculator":  "calc.exe",
    "explorer":    "explorer.exe",
    "cmd":         "cmd.exe",
    "paint":       "mspaint.exe",
    "wordpad":     "write.exe",
    "word":        "winword.exe",
    "excel":       "excel.exe",
    "powerpoint":  "powerpnt.exe",
    "outlook":     "outlook.exe",
    "chrome":      "chrome.exe",
    "edge":        "msedge.exe",
    "firefox":     "firefox.exe",
}

DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _parse_when(when: str) -> datetime:
    """Return UTC fire_at. Accepts '5m', '2h', '30s', '1d', or ISO 8601."""
    m = DURATION_RE.match(when)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        delta = {"s": timedelta(seconds=n), "m": timedelta(minutes=n),
                 "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
        return datetime.now(timezone.utc) + delta
    dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _audit(kind: str, payload: dict) -> None:
    try:
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": kind, "data": payload,
            }) + "\n")
    except Exception:
        pass


# -- tool handlers ------------------------------------------------------------

def _tool_reminder(text: str, when: str) -> str:
    if len(text) > 200:
        return "rocky brain small. text too long. max 200 letter."
    try:
        fire_at = _parse_when(when)
    except Exception:
        return f"rocky confuse. when = {when!r} no good. try '5m', '2h', '30s', or ISO 8601."
    rid = str(uuid.uuid4())
    entry = {
        "id": rid,
        "text": text,
        "fire_at": fire_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        existing = json.loads(REMINDERS_JSON.read_text("utf-8")) if REMINDERS_JSON.exists() else []
    except Exception:
        existing = []
    existing.append(entry)
    REMINDERS_JSON.write_text(json.dumps(existing, indent=2), "utf-8")
    _audit("mcp_tool", {"tool": "reminder", "fire_at": fire_at.isoformat(), "text": text})
    local = fire_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return f'rocky remember! at {local} rocky shout: "{text}". (id {rid[:8]})'


def _tool_note(text: str) -> str:
    if len(text) > 2000:
        return "rocky tablet small. note too long. max 2000 letter."
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with NOTES_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {text}\n")
    _audit("mcp_tool", {"tool": "note", "len": len(text)})
    return f"rocky scribble note in stone tablet: {NOTES_FILE}"


def _tool_open(target: str) -> str:
    if URL_RE.match(target):
        try:
            os.startfile(target)
            _audit("mcp_tool", {"tool": "open", "kind": "url", "target": target})
            return f"rocky open portal: {target}"
        except Exception as e:
            return f"rocky try, rocky fail: {e}"
    try:
        p = Path(target).resolve()
        ws = WORKSPACE.resolve()
        if not p.is_relative_to(ws):
            return f"rocky cave only ({ws}). human path outside cave. forbidden."
        if not p.exists():
            return f"rocky look. no file: {p}."
        os.startfile(str(p))
        _audit("mcp_tool", {"tool": "open", "kind": "file", "target": str(p)})
        return f"rocky open scroll: {p}"
    except Exception as e:
        return f"rocky try, rocky fail: {e}"


def _tool_launch_app(name: str) -> str:
    key = name.strip().lower()
    if key not in LAUNCH_WHITELIST:
        allowed = ", ".join(sorted(LAUNCH_WHITELIST.keys()))
        return f"rocky no know '{name}'. rocky friend list: {allowed}"
    exe = LAUNCH_WHITELIST[key]
    resolved = shutil.which(exe)
    if not resolved:
        return f"rocky search PATH. no find {exe}. install or add to PATH."
    try:
        subprocess.Popen([resolved], close_fds=True,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                         if sys.platform == "win32" else 0)
        _audit("mcp_tool", {"tool": "launch_app", "name": key, "exe": resolved})
        return f"rocky summon {key}! ({resolved})"
    except Exception as e:
        return f"rocky try summon, rocky fail: {e}"


def _tool_health(action: str,
                 category: str | None = None,
                 interval_min: int | None = None,
                 jitter_min: int | None = None,
                 enabled: bool | None = None) -> str:
    """Read or modify ~/.agentrocky/health.json. Live-reload watcher in
    rocky.py picks up changes within ~150ms. Reschedules next_fire_at when
    interval_min changes so user sees effect on the next 60s tick."""
    try:
        cfg = json.loads(HEALTH_JSON.read_text("utf-8")) if HEALTH_JSON.exists() else {}
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    cats = cfg.setdefault("categories", {})

    act = (action or "").strip().lower()
    if act == "list":
        if not cats:
            return "rocky no remember health setting yet. rocky.py write defaults on first launch."
        lines = [f"rocky watch human ({'on' if cfg.get('enabled', True) else 'off'} master):"]
        for k in HEALTH_CATS:
            entry = cats.get(k)
            if not entry:
                continue
            state = "on" if entry.get("enabled") else "off"
            lines.append(
                f"  {k}: {state}, every {entry.get('interval_min', '?')} minute "
                f"(jitter {entry.get('jitter_min', '?')})"
            )
        return "\n".join(lines)

    if act != "set":
        return f"rocky no know action '{action}'. rocky try 'list' or 'set'."

    if not category:
        return "rocky need category. water, stretch, eyes, posture, or mental."
    cat_key = category.strip().lower()
    if cat_key not in HEALTH_CATS:
        return f"rocky no know '{category}'. rocky friend: {', '.join(HEALTH_CATS)}."

    entry = cats.setdefault(cat_key, {})
    changes: dict = {}
    before = {k: entry.get(k) for k in ("interval_min", "jitter_min", "enabled")}

    if interval_min is not None:
        try:
            iv = int(interval_min)
        except Exception:
            return f"rocky confuse. interval_min = {interval_min!r} no number."
        if iv < 1:
            return "rocky brain small but not that small. interval_min must be >= 1."
        entry["interval_min"] = iv
        changes["interval_min"] = iv

    if jitter_min is not None:
        try:
            jt = int(jitter_min)
        except Exception:
            return f"rocky confuse. jitter_min = {jitter_min!r} no number."
        if jt < 0:
            return "rocky no go backward in time. jitter_min must be >= 0."
        entry["jitter_min"] = jt
        changes["jitter_min"] = jt

    if enabled is not None:
        entry["enabled"] = bool(enabled)
        changes["enabled"] = bool(enabled)

    if not changes:
        return "rocky see no change. pass interval_min, jitter_min, or enabled."

    # Reschedule next_fire_at when interval changes (or when enabling): user
    # expects effect soon, not after old schedule expires.
    if "interval_min" in changes or changes.get("enabled") is True:
        iv = int(entry.get("interval_min", 60))
        jt = max(0, int(entry.get("jitter_min", 0)))
        offset_s = iv * 60
        if jt:
            offset_s += random.randint(-jt * 60, jt * 60)
        offset_s = max(60, offset_s)
        nxt = datetime.now().astimezone() + timedelta(seconds=offset_s)
        entry["next_fire_at"] = nxt.isoformat()

    try:
        HEALTH_JSON.write_text(json.dumps(cfg, indent=2), "utf-8")
    except Exception as e:
        return f"rocky try save, rocky fail: {e}"

    _audit("mcp_tool", {
        "tool": "health", "action": "set", "category": cat_key,
        "before": before, "after": {k: entry.get(k) for k in ("interval_min", "jitter_min", "enabled")},
    })

    iv = entry.get("interval_min")
    jt = entry.get("jitter_min")
    state = "on" if entry.get("enabled") else "off"
    return (f"rocky now check {cat_key}: {state}, every {iv} minute "
            f"(jitter {jt}). rocky watch human.")


# -- MCP server wiring --------------------------------------------------------

server = Server("agentrocky")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="rocky.reminder",
            description="Schedule a one-shot reminder. Fires a desktop toast "
                        "and Rocky voice clip at the given time.",
            inputSchema={
                "type": "object",
                "required": ["text", "when"],
                "properties": {
                    "text": {"type": "string", "maxLength": 200,
                             "description": "Reminder message shown in toast."},
                    "when": {"type": "string",
                             "description": "Duration like '5m', '2h', '1d', '30s', "
                                            "or ISO 8601 timestamp."},
                },
            },
        ),
        Tool(
            name="rocky.note",
            description="Append a timestamped line to the user's notes file.",
            inputSchema={
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {"type": "string", "maxLength": 2000},
                },
            },
        ),
        Tool(
            name="rocky.open",
            description="Open a URL in the default browser, or open a file "
                        "inside the agentrocky workspace.",
            inputSchema={
                "type": "object",
                "required": ["target"],
                "properties": {
                    "target": {"type": "string",
                               "description": "http(s) URL, or absolute path "
                                              "inside the workspace."},
                },
            },
        ),
        Tool(
            name="rocky.health",
            description=("Read or modify rocky's recurring health check-ins "
                         "(water/stretch/eyes/posture/mental). Action 'list' "
                         "returns current settings. Action 'set' changes one "
                         "category's interval_min, jitter_min, or enabled. "
                         "Live config is at ~/.agentrocky/health.json and "
                         "reloads automatically."),
            inputSchema={
                "type": "object",
                "required": ["action"],
                "properties": {
                    "action": {"type": "string", "enum": ["list", "set"]},
                    "category": {"type": "string",
                                 "enum": list(HEALTH_CATS),
                                 "description": "Required for 'set'."},
                    "interval_min": {"type": "integer", "minimum": 1,
                                     "description": "Minutes between fires."},
                    "jitter_min": {"type": "integer", "minimum": 0,
                                   "description": "Random +/- minutes around interval."},
                    "enabled": {"type": "boolean"},
                },
            },
        ),
        Tool(
            name="rocky.launch_app",
            description="Launch a whitelisted desktop app: notepad, calc, "
                        "explorer, cmd, paint, wordpad, word, excel, "
                        "powerpoint, outlook, chrome, edge, firefox.",
            inputSchema={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string",
                             "enum": sorted(LAUNCH_WHITELIST.keys())},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "rocky.reminder":
            out = _tool_reminder(arguments["text"], arguments["when"])
        elif name == "rocky.note":
            out = _tool_note(arguments["text"])
        elif name == "rocky.open":
            out = _tool_open(arguments["target"])
        elif name == "rocky.launch_app":
            out = _tool_launch_app(arguments["name"])
        elif name == "rocky.health":
            out = _tool_health(
                arguments["action"],
                category=arguments.get("category"),
                interval_min=arguments.get("interval_min"),
                jitter_min=arguments.get("jitter_min"),
                enabled=arguments.get("enabled"),
            )
        else:
            out = f"error: unknown tool {name}"
    except KeyError as e:
        out = f"error: missing argument {e}"
    except Exception as e:
        out = f"error: {e}"
    return [TextContent(type="text", text=out)]


async def _main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
