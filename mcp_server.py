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
NOTES_FILE = WORKSPACE / "notes.md"

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
        return "error: text too long (max 200 chars)"
    try:
        fire_at = _parse_when(when)
    except Exception:
        return f"error: could not parse 'when' = {when!r}. use '5m', '2h', '30s', or ISO 8601."
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
    return f"reminder set for {local} (id={rid[:8]}): {text}"


def _tool_note(text: str) -> str:
    if len(text) > 2000:
        return "error: text too long (max 2000 chars)"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with NOTES_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {text}\n")
    _audit("mcp_tool", {"tool": "note", "len": len(text)})
    return f"note appended to {NOTES_FILE}"


def _tool_open(target: str) -> str:
    if URL_RE.match(target):
        try:
            os.startfile(target)
            _audit("mcp_tool", {"tool": "open", "kind": "url", "target": target})
            return f"opened url: {target}"
        except Exception as e:
            return f"error: {e}"
    try:
        p = Path(target).resolve()
        ws = WORKSPACE.resolve()
        if not p.is_relative_to(ws):
            return f"error: path outside workspace ({ws}). only urls or files inside workspace allowed."
        if not p.exists():
            return f"error: file not found: {p}"
        os.startfile(str(p))
        _audit("mcp_tool", {"tool": "open", "kind": "file", "target": str(p)})
        return f"opened file: {p}"
    except Exception as e:
        return f"error: {e}"


def _tool_launch_app(name: str) -> str:
    key = name.strip().lower()
    if key not in LAUNCH_WHITELIST:
        allowed = ", ".join(sorted(LAUNCH_WHITELIST.keys()))
        return f"error: '{name}' not whitelisted. allowed: {allowed}"
    exe = LAUNCH_WHITELIST[key]
    resolved = shutil.which(exe)
    if not resolved:
        return f"error: {exe} not found in PATH. install or add to PATH."
    try:
        subprocess.Popen([resolved], close_fds=True,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                         if sys.platform == "win32" else 0)
        _audit("mcp_tool", {"tool": "launch_app", "name": key, "exe": resolved})
        return f"launched {key} ({resolved})"
    except Exception as e:
        return f"error: {e}"


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
