"""
agentrocky — Windows port (Python + PyQt6)

Original macOS/Swift app: https://github.com/itmesneha/agentrocky by @itmesneha.
This is an unofficial Windows rebuild. Behavior mirrors the upstream README and
Swift sources; not a line-by-line port. Sprites are reused from the original repo
and must be placed in ./sprites/ next to this script.

Run: pythonw rocky.py
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == "win32":
    import winsound
else:
    winsound = None  # type: ignore

from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QObject, pyqtSignal, QSize, QRectF, QSharedMemory,
    QElapsedTimer, QFileSystemWatcher, QAbstractNativeEventFilter,
)
from PyQt6.QtGui import (
    QPixmap, QTransform, QPainter, QColor, QFont, QFontDatabase,
    QPainterPath, QPen, QBrush, QTextCursor, QIcon, QGuiApplication, QCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPlainTextEdit, QPushButton, QMessageBox,
    QSystemTrayIcon, QMenu,
)


# -- constants ----------------------------------------------------------------

def _bundle_dir() -> Path:
    """Bundled-resource root. PyInstaller exposes _MEIPASS; source uses script dir."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent))


def _external_dir() -> Path:
    """User-supplied resource root. Frozen: dir of .exe. Source: script dir."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def resource_path(rel: str) -> Path:
    """For files we ship (bundled into the exe via PyInstaller datas)."""
    return _bundle_dir() / rel


def external_path(rel: str) -> Path:
    """For files the end-user drops next to the exe (e.g. sprites)."""
    return _external_dir() / rel


SPRITE_DIR = external_path("sprites")
SOUND_DIR = resource_path("sounds")
SPRITE_FILES = {
    "stand": "stand.png",
    "walk1": "walkleft1.png",
    "walk2": "walkleft2.png",
    "jazz1": "jazz1.png",
    "jazz2": "jazz2.png",
    "jazz3": "jazz3.png",
}
SPRITE_SIZE = 96
WALK_SPEED_PX = 3.0            # per 33ms tick → ~90px/s
TASKBAR_OFFSET = 50            # gap above bottom of screen
JAZZ_DURATION_MS = 2400
JAZZ_FRAME_MS = 150
WALK_FRAME_MS = 125            # 8fps
MOVE_TICK_MS = 33              # 30fps — halves idle wakeups vs 60fps
BUBBLE_HIDE_MS = 3000
IDLE_JAZZ_MIN_MS = 15000
IDLE_JAZZ_MAX_MS = 45000

TOOL_BUBBLES = [
    "rocky building", "rocky do big science", "rocky thinking",
    "rocky compute", "rocky on it",
]
DONE_BUBBLES = ["rocky done!", "fist my bump", "rocky win", "task complete"]

# colors (retro terminal)
COLOR_BG = "#0A0A0A"
COLOR_TEXT = "#33FF66"
COLOR_TOOL = "#66CCFF"
COLOR_SYS = "#669977"
COLOR_ERR = "#FF6666"

# sandboxed working dir for claude — overrideable via env var
WORKSPACE = Path(os.environ.get("AGENTROCKY_CWD") or (Path.home() / "agentrocky-workspace"))

# audit log: user sends + tool_use blocks only
AUDIT_DIR = Path.home() / ".agentrocky"
AUDIT_LOG = AUDIT_DIR / "audit.log"
CRASH_LOG = AUDIT_DIR / "log.txt"
REMINDERS_JSON = AUDIT_DIR / "reminders.json"
MCP_CONFIG_JSON = AUDIT_DIR / "mcp_config.json"
MCP_SERVER_PY = resource_path("mcp_server.py")
MCP_SERVER_EXE = Path(sys.executable).parent / "mcp_server.exe"
HEALTH_JSON = AUDIT_DIR / "health.json"

# Health check-in scheduler — local recurring nudges (water/stretch/eyes/etc.)
HEALTH_TICK_MS = 60_000
HEALTH_DEFAULT_CATS = {
    "water":   {"enabled": True,  "interval_min": 60,  "jitter_min": 10,
                "copy": "rocky thirsty. human drink water, question?"},
    "stretch": {"enabled": True,  "interval_min": 90,  "jitter_min": 15,
                "copy": "rocky stiff. human stretch, question?"},
    "eyes":    {"enabled": True,  "interval_min": 20,  "jitter_min": 5,
                "copy": "eye tired. human look far thing 20 second, question?"},
    "posture": {"enabled": False, "interval_min": 45,  "jitter_min": 10,
                "copy": "rocky see slouch. human sit straight, question?"},
    "mental":  {"enabled": True,  "interval_min": 120, "jitter_min": 20,
                "copy": "rocky check human mood. human ok, question?"},
}


def _write_mcp_config() -> Path:
    """Write the local MCP config that points claude at our sidecar server."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    if getattr(sys, "frozen", False):
        command = str(MCP_SERVER_EXE)
        args: list[str] = []
    else:
        command = sys.executable
        args = [str(MCP_SERVER_PY)]
    cfg = {
        "mcpServers": {
            "agentrocky": {
                "command": command,
                "args": args,
                "env": {
                    "AGENTROCKY_CWD": str(WORKSPACE),
                },
            }
        }
    }
    MCP_CONFIG_JSON.write_text(json.dumps(cfg, indent=2), "utf-8")
    return MCP_CONFIG_JSON


LOG_MAX_BYTES = 5 * 1024 * 1024  # rotate audit.log / log.txt at 5MB → .1


def _rotate_if_big(path: Path, max_bytes: int = LOG_MAX_BYTES) -> None:
    """Single-generation rotation. If path > max_bytes → overwrite path.1, fresh file."""
    try:
        if path.exists() and path.stat().st_size > max_bytes:
            backup = path.with_suffix(path.suffix + ".1")
            try:
                if backup.exists():
                    backup.unlink()
            except Exception:
                pass
            path.replace(backup)
    except Exception:
        pass


def _install_excepthook() -> None:
    """Route unhandled exceptions to ~/.agentrocky/log.txt + a dialog."""
    import traceback

    def hook(etype, value, tb):
        try:
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            _rotate_if_big(CRASH_LOG)
            with CRASH_LOG.open("a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now(timezone.utc).isoformat()} ---\n")
                traceback.print_exception(etype, value, tb, file=f)
        except Exception:
            pass
        # Marshal the dialog to the GUI thread — reader threads must not call
        # QMessageBox directly. QTimer.singleShot(0, ...) posts to the main
        # event loop. If no QApplication yet (very early crash), skip dialog.
        try:
            msg = f"Unhandled error: {etype.__name__}: {value}\n\nLog: {CRASH_LOG}"
            if QApplication.instance() is not None:
                QTimer.singleShot(0, lambda m=msg: QMessageBox.critical(
                    None, "agentrocky crashed", m,
                ))
        except Exception:
            pass
        sys.__excepthook__(etype, value, tb)

    sys.excepthook = hook


_audit_buffer: list[str] = []
_audit_lock = threading.Lock()
_audit_flush_count = 0


def audit(kind: str, payload) -> None:
    """Buffered append. Real disk write happens in flush_audit (1s timer +
    aboutToQuit final flush). Thread-safe — called from reader threads too."""
    try:
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "data": payload,
        }) + "\n"
    except Exception:
        return
    with _audit_lock:
        _audit_buffer.append(line)


def flush_audit() -> None:
    global _audit_flush_count
    with _audit_lock:
        if not _audit_buffer:
            return
        chunk = "".join(_audit_buffer)
        _audit_buffer.clear()
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        if _audit_flush_count % 50 == 0:
            _rotate_if_big(AUDIT_LOG)
        _audit_flush_count += 1
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(chunk)
    except Exception:
        pass  # never let logging break the app


_toast_notifier = None
_toast_classes: tuple | None = None  # (ToastNotification, XmlDocument)
_toast_disabled = False


def show_toast(title: str, body: str) -> bool:
    """Native Win10/11 toast. Returns False if winrt unavailable / fails.

    Imports winrt lazily on first call, caches the notifier + classes so
    subsequent calls skip the import dance.
    """
    global _toast_notifier, _toast_classes, _toast_disabled
    if sys.platform != "win32" or _toast_disabled:
        return False
    if _toast_notifier is None:
        try:
            from winrt.windows.ui.notifications import (
                ToastNotification, ToastNotificationManager,
            )
            from winrt.windows.data.xml.dom import XmlDocument
            _toast_classes = (ToastNotification, XmlDocument)
            _toast_notifier = ToastNotificationManager.create_toast_notifier_with_id(
                "agentrocky"
            )
        except Exception:
            _toast_disabled = True
            return False
    try:
        from html import escape
        ToastNotification, XmlDocument = _toast_classes  # type: ignore[misc]
        xml = (
            "<toast><visual><binding template='ToastGeneric'>"
            f"<text>{escape(title)}</text>"
            f"<text>{escape(body)}</text>"
            "</binding></visual></toast>"
        )
        doc = XmlDocument()
        doc.load_xml(xml)
        _toast_notifier.show(ToastNotification(doc))
        return True
    except Exception:
        return False


def mono_font(size: int = 12) -> QFont:
    for fam in ("Cascadia Code", "Cascadia Mono", "Consolas", "Courier New"):
        if fam in QFontDatabase.families():
            f = QFont(fam, size)
            f.setStyleHint(QFont.StyleHint.Monospace)
            return f
    f = QFont()
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSize(size)
    return f


# -- voice pack ---------------------------------------------------------------

# Higher number = more important. Higher pri preempts lower; same pri within
# VOICE_MIN_GAP_MS of an in-flight clip is dropped (prevents stutter).
VOICE_PRIORITY = {
    "session_start": 1,
    "task_acknowledge": 2,
    "task_complete": 3,
    "task_error": 4,
}
VOICE_MIN_GAP_MS = 600


def _wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate() or 1
            return int(round(frames / rate * 1000))
    except Exception:
        return 1500  # safe default if parse fails


def _now_ms() -> int:
    return time.monotonic_ns() // 1_000_000


class VoicePack:
    """Lifecycle SFX. Random clip per category. winsound playback (async).

    Manifest schema: {"clips": [{"category": str, "file": str, ...}, ...]}.
    Scheduler avoids clobber: tracks an in-flight clip's end-time and priority,
    drops/preempts subsequent plays based on category priority + cool-down.
    """

    def __init__(self, base: Path) -> None:
        self.base = base
        self.enabled = sys.platform == "win32" and winsound is not None
        self.by_category: dict[str, list[Path]] = {}
        self.durations: dict[Path, int] = {}
        self._busy_until_ms: int = 0
        self._current_priority: int = 0
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
                # durations parsed lazily on first play (avoid startup wave-open per clip)
        if not self.by_category:
            self.enabled = False

    def _duration_ms(self, clip: Path) -> int:
        d = self.durations.get(clip)
        if d is None:
            d = _wav_duration_ms(clip)
            self.durations[clip] = d
        return d

    def play(self, category: str) -> None:
        if not self.enabled:
            return
        clips = self.by_category.get(category)
        if not clips:
            return
        pri = VOICE_PRIORITY.get(category, 0)
        now = _now_ms()
        if now < self._busy_until_ms:
            remaining = self._busy_until_ms - now
            if pri < self._current_priority:
                return  # don't interrupt more important clip
            if pri == self._current_priority and remaining > VOICE_MIN_GAP_MS:
                return  # same tier, too close — drop to avoid stutter
            # else: higher priority, or same-tier with clip nearly done → preempt
        clip = random.choice(clips)
        try:
            winsound.PlaySound(str(clip),
                               winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            return  # never let audio break the app
        self._busy_until_ms = now + self._duration_ms(clip)
        self._current_priority = pri

    def stop(self) -> None:
        self._busy_until_ms = 0
        self._current_priority = 0
        if sys.platform == "win32" and winsound is not None:
            try:
                winsound.PlaySound(None, 0)
            except Exception:
                pass

    def toggle(self) -> bool:
        if not self.by_category:
            return False  # nothing to enable
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()
        return self.enabled


# -- claude subprocess --------------------------------------------------------

class ClaudeSession(QObject):
    """Persistent `claude` CLI subprocess in stream-json mode.

    Reader threads emit signals only — never touch widgets directly.
    """

    line_received = pyqtSignal(str, str)   # (text, kind: text|tool|system|error)
    task_complete = pyqtSignal()
    tool_use_seen = pyqtSignal(str)        # tool name
    ready = pyqtSignal()
    session_died = pyqtSignal()            # stdout EOF / process exit
    usage_updated = pyqtSignal(dict)       # cumulative usage from result.usage

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.proc: subprocess.Popen | None = None
        self._stdin_lock = threading.Lock()
        self._usage_total = {"input_tokens": 0, "output_tokens": 0,
                             "cache_read_input_tokens": 0,
                             "cache_creation_input_tokens": 0}

    @staticmethod
    def _locate_cli() -> list[str] | None:
        for name in ("claude.cmd", "claude.exe", "claude"):
            p = shutil.which(name)
            if p:
                return [p]
        appdata = os.environ.get("APPDATA")
        if appdata:
            cand = Path(appdata) / "npm" / "claude.cmd"
            if cand.exists():
                return [str(cand)]
        # last resort: WSL
        wsl = shutil.which("wsl")
        if wsl:
            return [wsl, "claude"]
        return None

    def start(self) -> bool:
        argv = self._locate_cli()
        if not argv:
            self.line_received.emit(
                "claude CLI not found. Install via npm i -g @anthropic-ai/claude-code "
                "or ensure WSL has it.", "error",
            )
            return False
        argv = argv + [
            "-p",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        if MCP_CONFIG_JSON.exists():
            argv += ["--mcp-config", str(MCP_CONFIG_JSON)]
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0x08000000  # CREATE_NO_WINDOW
        try:
            self.proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(WORKSPACE),
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except Exception as e:
            self.line_received.emit(f"failed to launch claude: {e}", "error")
            return False

        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        return True

    def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        for raw in self.proc.stdout:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # CLI may emit a non-JSON banner; surface as system text
                self.line_received.emit(line, "system")
                continue
            self._dispatch(msg)
        # stdout closed → session ended (intentionally or otherwise)
        if self.proc is not None:
            self.session_died.emit()

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for raw in self.proc.stderr:
            line = raw.rstrip("\r\n")
            if line:
                self.line_received.emit(line, "error")

    def _dispatch(self, msg: dict) -> None:
        t = msg.get("type")
        if t == "system":
            # init subtype signals readiness
            if msg.get("subtype") == "init":
                self.ready.emit()
            return
        if t == "user":
            return  # echoes / tool_results — ignore
        if t == "assistant":
            content = (msg.get("message") or {}).get("content") or []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text = (block.get("text") or "").rstrip()
                    if text:
                        self.line_received.emit(text, "text")
                elif btype == "tool_use":
                    name = block.get("name") or "tool"
                    self.line_received.emit(f"→ {name}", "tool")
                    self.tool_use_seen.emit(name)
                    audit("tool_use", {
                        "name": name,
                        "input": block.get("input"),
                        "id": block.get("id"),
                    })
            return
        if t == "result":
            usage = msg.get("usage") or {}
            for k in self._usage_total:
                v = usage.get(k)
                if isinstance(v, int):
                    self._usage_total[k] += v
            self.usage_updated.emit(dict(self._usage_total))
            self.task_complete.emit()
            return

    def is_alive(self) -> bool:
        return bool(self.proc and self.proc.poll() is None and self.proc.stdin)

    def reset_usage(self) -> None:
        for k in self._usage_total:
            self._usage_total[k] = 0
        self.usage_updated.emit(dict(self._usage_total))

    def send(self, prompt: str) -> None:
        if not self.is_alive():
            self.line_received.emit(
                "session is not running — use Restart Claude from the tray menu.",
                "error",
            )
            self.session_died.emit()
            return
        envelope = {
            "type": "user",
            "message": {"role": "user", "content": prompt},
        }
        data = json.dumps(envelope) + "\n"
        audit("user_send", {"content": prompt})
        with self._stdin_lock:
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except Exception as e:
                self.line_received.emit(f"send failed: {e}", "error")
                self.session_died.emit()

    def stop(self) -> None:
        """Cleanly terminate the claude subprocess. Safe to call multiple times."""
        proc = self.proc
        if not proc:
            return
        self.proc = None
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# -- speech bubble ------------------------------------------------------------

BUBBLE_MAX_WIDTH = 280
BUBBLE_DEBOUNCE_MS = 400


class SpeechBubble(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._text = ""
        self._last_shown_ms = 0
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, anchor_center_x: int, anchor_top_y: int,
                  persistent: bool = False) -> None:
        # debounce: drop if a bubble appeared too recently (prevents flicker on tool spam).
        # Persistent bubbles bypass debounce — health checks must always show.
        if not hasattr(self, "_etimer"):
            self._etimer = QElapsedTimer()
            self._etimer.start()
        if (not persistent and self.isVisible()
                and self._etimer.elapsed() - self._last_shown_ms < BUBBLE_DEBOUNCE_MS):
            return
        self._last_shown_ms = self._etimer.elapsed()

        self._text = text
        fm = self.fontMetrics()
        max_inner = BUBBLE_MAX_WIDTH - 24
        # measure with word wrap inside the max width
        rect = fm.boundingRect(0, 0, max_inner, 10_000,
                               int(Qt.TextFlag.TextWordWrap)
                               | int(Qt.AlignmentFlag.AlignCenter), text)
        w = max(rect.width() + 24, 60)
        h = rect.height() + 18 + 8  # padding + tail
        self.resize(w, h)
        self.move(int(anchor_center_x - w / 2), int(anchor_top_y - h))
        self.update()
        self.show()
        self.raise_()
        self._hide_timer.stop()
        if not persistent:
            self._hide_timer.start(BUBBLE_HIDE_MS)

    def dismiss(self) -> None:
        self._hide_timer.stop()
        self.hide()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        body = QRectF(0, 0, w, h - 8)
        path = QPainterPath()
        path.addRoundedRect(body, 8, 8)
        cx = w / 2
        tail = QPainterPath()
        tail.moveTo(cx - 6, h - 8)
        tail.lineTo(cx, h)
        tail.lineTo(cx + 6, h - 8)
        tail.closeSubpath()
        path.addPath(tail)
        p.setBrush(QBrush(QColor(255, 255, 255, 235)))
        p.setPen(QPen(QColor(40, 40, 40), 1))
        p.drawPath(path)
        p.setPen(QColor(20, 20, 20))
        p.setFont(self.font())
        # word-wrap text inside body (with small horizontal padding)
        body_padded = body.adjusted(8, 4, -8, -4)
        p.drawText(body_padded,
                   int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignCenter),
                   self._text)


# -- chat window --------------------------------------------------------------

class ChatHeader(QWidget):
    """Draggable title bar for the chat window."""

    def __init__(self, parent: "ChatWindow") -> None:
        super().__init__(parent)
        self._parent_win = parent
        self._drag_offset: QPoint | None = None
        self.setFixedHeight(28)
        self.setStyleSheet("background:#111; color:#33FF66;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        title = QLabel("● rocky-terminal")
        title.setFont(mono_font(11))
        title.setStyleSheet("color:#33FF66;")
        lay.addWidget(title)
        lay.addStretch(1)
        # token counter — updated via ChatWindow.set_usage
        self.tokens_label = QLabel("")
        self.tokens_label.setFont(mono_font(10))
        self.tokens_label.setStyleSheet(f"color:{COLOR_SYS};")
        lay.addWidget(self.tokens_label)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setFont(mono_font(14))
        close_btn.setStyleSheet(
            "QPushButton{color:#FF6666;background:transparent;border:none;}"
            "QPushButton:hover{color:#FFAAAA;}"
        )
        close_btn.clicked.connect(parent.hide)
        lay.addWidget(close_btn)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                ev.globalPosition().toPoint() - self._parent_win.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._drag_offset is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self._parent_win.move(ev.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _ev) -> None:  # noqa: N802
        self._drag_offset = None


class HistoryLineEdit(QPlainTextEdit):
    """Multi-line input with shell-style Up/Down history.

    Enter submits; Shift+Enter inserts a newline. Up/Down nav history when
    cursor is on the first/last visual line (mirrors zsh/fish behaviour).
    Auto-grows up to MAX_LINES, then scrolls.
    """

    HISTORY_CAP = 500
    MAX_LINES = 6
    submitted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._idx: int | None = None
        self._draft = ""
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabChangesFocus(True)
        self.document().contentsChanged.connect(self._fit_height)
        self._fit_height()

    # --- API parity with prior QLineEdit-based version ---
    def text(self) -> str:
        return self.toPlainText()

    def setText(self, value: str) -> None:  # noqa: N802
        self.setPlainText(value)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def clear(self) -> None:
        self.setPlainText("")

    def push(self, text: str) -> None:
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
            if len(self._history) > self.HISTORY_CAP:
                del self._history[: len(self._history) - self.HISTORY_CAP]
        self._idx = None
        self._draft = ""

    # --- key handling ---
    def keyPressEvent(self, ev) -> None:  # noqa: N802
        key = ev.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(ev)
                return
            self.submitted.emit()
            return
        if key == Qt.Key.Key_Up and self._history:
            cur = self.textCursor()
            if cur.blockNumber() == 0:
                if self._idx is None:
                    self._draft = self.toPlainText()
                    self._idx = len(self._history) - 1
                elif self._idx > 0:
                    self._idx -= 1
                self.setText(self._history[self._idx])
                return
        if key == Qt.Key.Key_Down and self._idx is not None:
            cur = self.textCursor()
            if cur.blockNumber() == self.document().blockCount() - 1:
                if self._idx < len(self._history) - 1:
                    self._idx += 1
                    self.setText(self._history[self._idx])
                else:
                    self._idx = None
                    self.setText(self._draft)
                return
        super().keyPressEvent(ev)

    def _fit_height(self) -> None:
        fm = self.fontMetrics()
        line_h = fm.lineSpacing()
        n = max(1, min(self.MAX_LINES, self.document().blockCount()))
        # padding ~6px top + bottom
        self.setFixedHeight(line_h * n + 10)


class ChatWindow(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.resize(420, 520)
        self.setStyleSheet(f"background:{COLOR_BG};")
        self._opted_in = False  # one-time --dangerously-skip-permissions ack
        self._is_running = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(ChatHeader(self))

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(mono_font(11))
        self.output.setStyleSheet(
            f"QTextEdit{{background:{COLOR_BG};color:{COLOR_TEXT};border:none;"
            f"padding:8px;}}"
        )
        # cap scrollback so long sessions don't bloat memory
        self.output.document().setMaximumBlockCount(5000)
        root.addWidget(self.output, 1)

        # streaming cursor: visible only while a turn is in flight
        self.cursor_label = QLabel("▋")
        self.cursor_label.setFont(mono_font(11))
        self.cursor_label.setStyleSheet(
            f"color:{COLOR_TEXT};background:{COLOR_BG};padding:0 10px 4px 10px;"
        )
        self.cursor_label.hide()
        root.addWidget(self.cursor_label)

        bar = QWidget()
        bar.setStyleSheet("background:#000;")
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(10, 6, 10, 8)
        prompt = QLabel("❯")
        prompt.setFont(mono_font(12))
        prompt.setStyleSheet(f"color:{COLOR_TEXT};")
        bar_lay.addWidget(prompt)
        self.input = HistoryLineEdit()
        self.input.setFont(mono_font(11))
        self.input.setStyleSheet(
            f"QPlainTextEdit{{background:transparent;color:{COLOR_TEXT};"
            f"border:none;}}"
        )
        self.input.submitted.connect(self._on_submit)
        bar_lay.addWidget(self.input, 1)
        root.addWidget(bar)

        # blink the cursor while running
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_state = True

        # batched line append — coalesce streamed lines, flush via 50ms timer
        self._pending_html: list[str] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.timeout.connect(self._flush_lines)

    def set_running(self, running: bool) -> None:
        self._is_running = running
        if running:
            self.cursor_label.show()
            self._blink_state = True
            self.cursor_label.setText("▋")
            self._blink_timer.start(500)
        else:
            self._blink_timer.stop()
            self.cursor_label.hide()

    def _blink(self) -> None:
        self._blink_state = not self._blink_state
        self.cursor_label.setText("▋" if self._blink_state else " ")

    def set_usage(self, usage: dict) -> None:
        header = self.findChild(ChatHeader)
        if header is None:
            return
        total_in = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) \
                   + usage.get("cache_creation_input_tokens", 0)
        total_out = usage.get("output_tokens", 0)
        header.tokens_label.setText(f"in {total_in:,}  out {total_out:,}")

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if ev.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        if ev.key() == Qt.Key.Key_L and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._pending_html.clear()
            self._flush_timer.stop()
            self.output.clear()
            return
        super().keyPressEvent(ev)

    def append_line(self, text: str, kind: str) -> None:
        color = {
            "text": COLOR_TEXT, "tool": COLOR_TOOL,
            "system": COLOR_SYS, "error": COLOR_ERR,
        }.get(kind, COLOR_TEXT)
        # escape minimal HTML
        safe = (text.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace("\n", "<br>"))
        self._pending_html.append(f'<div style="color:{color};">{safe}</div>')
        if not self._flush_timer.isActive():
            self._flush_timer.start(50)

    def _flush_lines(self) -> None:
        if not self._pending_html:
            return
        # only follow tail if user already at bottom — don't yank mid-scroll
        sb = self.output.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml("".join(self._pending_html))
        self._pending_html.clear()
        if at_bottom:
            self.output.moveCursor(QTextCursor.MoveOperation.End)
            sb.setValue(sb.maximum())

    def _on_submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        if not self._opted_in:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("agentrocky — read this first")
            box.setText("Claude will run with --dangerously-skip-permissions.")
            box.setInformativeText(
                f"Working directory: {WORKSPACE}\n\n"
                "Without permission prompts, Claude can:\n"
                "  • read and write any file under that directory\n"
                "  • run arbitrary shell commands (including delete / network)\n"
                "  • call MCP tools and external services\n"
                "  • send data to api.anthropic.com\n\n"
                "Conversations and tool inputs are also written to:\n"
                f"  {AUDIT_LOG}\n\n"
                "Only continue if you understand and accept this. The dialog "
                "won't show again this session."
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if box.exec() != QMessageBox.StandardButton.Ok:
                return
            self._opted_in = True
        self.input.push(text)
        self.input.clear()
        self.append_line(f"❯ {text}", "system")
        self.set_running(True)
        self.submitted.emit(text)


# -- rocky widget -------------------------------------------------------------

class Rocky(QWidget):
    def __init__(self, session: ClaudeSession) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("background: transparent;")
        self.resize(SPRITE_SIZE, SPRITE_SIZE)

        self.session = session
        self.sprites: dict[str, QPixmap] = {}
        self._load_sprites()
        self.voice = VoicePack(SOUND_DIR)

        self.label = QLabel(self)
        self.label.resize(SPRITE_SIZE, SPRITE_SIZE)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.label.setAutoFillBackground(False)
        self.label.setStyleSheet("background: transparent; border: none;")

        # state — pick the screen under the cursor (falls back to primary)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self._qscreen = screen
        scr = screen.availableGeometry()
        self._screen = scr
        self.pos_x = float(scr.left() + scr.width() // 3)
        self.pos_y = scr.bottom() - TASKBAR_OFFSET - SPRITE_SIZE
        # recompute on screen geometry change (DPI / resolution / dock changes)
        screen.geometryChanged.connect(self._on_screen_changed)
        screen.availableGeometryChanged.connect(self._on_screen_changed)
        self.direction = -1     # -1 left, +1 right (sprites face left by default)
        self.walk_frame = 0
        self.jazz_frame = 0
        self.is_jazzing = False
        self.is_chat_open = False
        self._chat_drag_origin: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._health_active = False
        self._health_category: str | None = None
        self._paused = False  # user toggle — stop walk + idle, snap to stand

        self.move(int(self.pos_x), int(self.pos_y))

        # bubble + chat
        self.bubble = SpeechBubble()
        self.chat = ChatWindow()
        self.chat.submitted.connect(self._on_user_send)

        # session signals
        session.line_received.connect(self.chat.append_line)
        session.task_complete.connect(self._on_task_complete)
        session.tool_use_seen.connect(self._on_tool_use)
        session.session_died.connect(self._on_session_died)
        session.usage_updated.connect(self.chat.set_usage)
        # readiness flag (no chat noise) — tooltip + first-send gate live elsewhere
        self._claude_ready = False
        session.ready.connect(self._on_claude_ready)

        # timers
        self.move_timer = QTimer(self)
        self.move_timer.timeout.connect(self._tick_move)
        self.move_timer.start(MOVE_TICK_MS)

        self.walk_timer = QTimer(self)
        self.walk_timer.timeout.connect(self._tick_walk_frame)
        self.walk_timer.start(WALK_FRAME_MS)

        self.jazz_timer = QTimer(self)
        self.jazz_timer.timeout.connect(self._tick_jazz_frame)

        self.jazz_stop_timer = QTimer(self)
        self.jazz_stop_timer.setSingleShot(True)
        self.jazz_stop_timer.timeout.connect(self._stop_jazz)

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._idle_tick)
        self._schedule_idle()

        # lock-screen detection — event-driven via WTSRegisterSessionNotification
        # (registered in showEvent once HWND is valid). Poll fallback removed.
        self._was_locked = False
        self._was_visible_pre_lock = True
        self._wts_registered = False
        self._msg_struct = None

        self._render()

    def showEvent(self, ev) -> None:  # noqa: N802
        super().showEvent(ev)
        if sys.platform == "win32":
            self._strip_win32_border()
            self._register_session_notification()

    def _strip_win32_border(self) -> None:
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_STYLE = -16
            GWL_EXSTYLE = -20
            WS_BORDER = 0x00800000
            WS_DLGFRAME = 0x00400000
            WS_THICKFRAME = 0x00040000
            WS_CAPTION = 0x00C00000
            WS_EX_DLGMODALFRAME = 0x00000001
            WS_EX_CLIENTEDGE = 0x00000200
            WS_EX_STATICEDGE = 0x00020000
            WS_EX_WINDOWEDGE = 0x00000100
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~(WS_BORDER | WS_DLGFRAME | WS_THICKFRAME | WS_CAPTION)
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex &= ~(WS_EX_DLGMODALFRAME | WS_EX_CLIENTEDGE
                    | WS_EX_STATICEDGE | WS_EX_WINDOWEDGE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE
                                | SWP_NOZORDER | SWP_FRAMECHANGED)
            try:
                dwm = ctypes.windll.dwmapi
                DWMWA_NCRENDERING_POLICY = 2
                DWMWA_BORDER_COLOR = 34
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMNCRP_DISABLED = 1
                DWMWCP_DONOTROUND = 1
                DWMWA_COLOR_NONE = 0xFFFFFFFE
                ncrp = ctypes.c_int(DWMNCRP_DISABLED)
                dwm.DwmSetWindowAttribute(
                    hwnd, DWMWA_NCRENDERING_POLICY,
                    ctypes.byref(ncrp), ctypes.sizeof(ncrp),
                )
                corner = ctypes.c_int(DWMWCP_DONOTROUND)
                dwm.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(corner), ctypes.sizeof(corner),
                )
                color = ctypes.c_uint(DWMWA_COLOR_NONE)
                dwm.DwmSetWindowAttribute(
                    hwnd, DWMWA_BORDER_COLOR,
                    ctypes.byref(color), ctypes.sizeof(color),
                )
            except Exception:
                pass
        except Exception:
            pass

    def _load_sprites(self) -> None:
        # render at native pixel density so sprites stay crisp on 4K / 200% scaling
        screen = (getattr(self, "_qscreen", None)
                  or QGuiApplication.screenAt(QCursor.pos())
                  or QApplication.primaryScreen())
        dpr = screen.devicePixelRatio() if screen else 1.0
        self._sprite_dpr = dpr
        target = max(1, int(round(SPRITE_SIZE * dpr)))
        for key, fname in SPRITE_FILES.items():
            path = SPRITE_DIR / fname
            pix = QPixmap(str(path))
            if pix.isNull():
                raise RuntimeError(f"failed to load sprite: {path}")
            scaled = pix.scaled(
                target, target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            self.sprites[key] = scaled
            # pre-flip to right-facing (avoids per-frame transformed() allocation)
            flipped = scaled.transformed(QTransform().scale(-1, 1))
            flipped.setDevicePixelRatio(dpr)
            self.sprites[key + "_r"] = flipped

    # -- rendering --
    def _current_pixmap(self) -> QPixmap:
        if self.is_jazzing:
            key = f"jazz{(self.jazz_frame % 3) + 1}"
        elif self.is_chat_open:
            key = "stand"
        else:
            key = "walk1" if self.walk_frame == 0 else "walk2"
        # sprites face left; pre-flipped right-facing variant cached as key + "_r"
        if self.direction > 0 and not self.is_chat_open:
            return self.sprites[key + "_r"]
        return self.sprites[key]

    def _render(self) -> None:
        self.label.setPixmap(self._current_pixmap())

    # -- timers --
    def _tick_move(self) -> None:
        if self.is_chat_open or self.is_jazzing or self._paused:
            return
        self.pos_x += WALK_SPEED_PX * self.direction
        scr = self._screen
        if self.pos_x <= scr.left():
            self.pos_x = scr.left()
            self.direction = 1
        elif self.pos_x + SPRITE_SIZE >= scr.right():
            self.pos_x = scr.right() - SPRITE_SIZE
            self.direction = -1
        self.move(int(self.pos_x), int(self.pos_y))

    def _tick_walk_frame(self) -> None:
        if self.is_jazzing or self.is_chat_open or self._paused:
            return
        self.walk_frame ^= 1
        self._render()

    def _tick_jazz_frame(self) -> None:
        self.jazz_frame += 1
        self._render()

    def _stop_jazz(self) -> None:
        self.is_jazzing = False
        self.jazz_timer.stop()
        self._render()

    def _start_jazz(self) -> None:
        if self.is_jazzing:
            return
        self.is_jazzing = True
        self.jazz_frame = 0
        self.jazz_timer.start(JAZZ_FRAME_MS)
        self.jazz_stop_timer.start(JAZZ_DURATION_MS)
        self._render()

    def _schedule_idle(self) -> None:
        self.idle_timer.start(random.randint(IDLE_JAZZ_MIN_MS, IDLE_JAZZ_MAX_MS))

    def _idle_tick(self) -> None:
        if (not self.is_chat_open and not self.is_jazzing
                and not self._health_active and not self._paused):
            self._start_jazz()
        self._schedule_idle()

    def set_paused(self, on: bool) -> None:
        if on == self._paused:
            return
        self._paused = on
        if on:
            self.move_timer.stop()
            self.walk_timer.stop()
            self.idle_timer.stop()
            if self.is_jazzing:
                self.jazz_timer.stop()
                self.jazz_stop_timer.stop()
                self.is_jazzing = False
            self.walk_frame = 0
            self._render()
        else:
            if not self.is_chat_open:
                self.move_timer.start(MOVE_TICK_MS)
                self.walk_timer.start(WALK_FRAME_MS)
                self._schedule_idle()
        if hasattr(self, "_tray_pause_action") and self._tray_pause_action is not None:
            self._tray_pause_action.setChecked(on)

    # -- bubble --
    def _show_bubble(self, text: str) -> None:
        cx = int(self.pos_x + SPRITE_SIZE / 2)
        top = int(self.pos_y) + 4
        self.bubble.show_text(text, cx, top)

    # -- health check ack flow --
    def show_health_check(self, category: str, text: str) -> None:
        """Freeze rocky + show persistent bubble. User clicks rocky to ack."""
        if not self.isVisible():
            return  # locked / hidden — toast already covers it
        self._health_active = True
        self._health_category = category
        # freeze motion (mirrors chat-open pause path)
        self.move_timer.stop()
        self.walk_timer.stop()
        # snap to stand sprite (no walk frame mid-step)
        self.walk_frame = 0
        self.is_jazzing = False
        self.jazz_timer.stop()
        self._render()
        cx = int(self.pos_x + SPRITE_SIZE / 2)
        top = int(self.pos_y) + 4
        self.bubble.show_text(text, cx, top, persistent=True)

    def _ack_health_check(self) -> None:
        if not self._health_active:
            return
        cat = self._health_category
        self.bubble.dismiss()
        self._health_active = False
        self._health_category = None
        if not self.is_chat_open and not self._paused:
            self.move_timer.start(MOVE_TICK_MS)
            self.walk_timer.start(WALK_FRAME_MS)
            self._schedule_idle()
        self.voice.play("session_start")
        audit("health_ack", {"category": cat})

    def hideEvent(self, ev) -> None:  # noqa: N802
        # Tray "Hide Rocky" or programmatic hide while health-active: clear
        # state silently so flag isn't stuck. No voice/audit.
        if self._health_active:
            self.bubble.dismiss()
            self._health_active = False
            self._health_category = None
        super().hideEvent(ev)

    # -- tray helpers --
    def show_chat(self) -> None:
        if not self.is_chat_open:
            self._toggle_chat()
        else:
            self.chat.raise_()
            self.chat.activateWindow()

    def _on_claude_ready(self) -> None:
        self._claude_ready = True
        if hasattr(self, "_tray") and self._tray is not None:
            self._tray.setToolTip("agentrocky — ready")
        self.voice.play("session_start")

    # -- session events --
    def _on_task_complete(self) -> None:
        self.chat.set_running(False)
        self._start_jazz()
        self._show_bubble(random.choice(DONE_BUBBLES))
        self.voice.play("task_complete")

    def _on_tool_use(self, _name: str) -> None:
        self._show_bubble(random.choice(TOOL_BUBBLES))

    def _on_user_send(self, text: str) -> None:
        self.session.send(text)
        self.voice.play("task_acknowledge")

    def _on_session_died(self) -> None:
        self.chat.set_running(False)
        self._claude_ready = False
        if hasattr(self, "_tray") and self._tray is not None:
            self._tray.setToolTip("agentrocky — session ended")
        self.chat.append_line(
            "[claude session ended — Restart Claude from the tray menu]",
            "error",
        )
        self.voice.play("task_error")

    def restart_claude(self) -> None:
        """Tear down and respawn the claude subprocess."""
        self.chat.append_line("[restarting claude…]", "system")
        self.session.stop()
        self.session.reset_usage()
        self._claude_ready = False
        if hasattr(self, "_tray") and self._tray is not None:
            self._tray.setToolTip("agentrocky — starting…")
        self.session.start()

    # -- lock screen (event-driven via WTSRegisterSessionNotification) --
    _WM_WTSSESSION_CHANGE = 0x02B1
    _WTS_SESSION_LOCK = 0x7
    _WTS_SESSION_UNLOCK = 0x8

    def _register_session_notification(self) -> None:
        if self._wts_registered or sys.platform != "win32":
            return
        try:
            import ctypes
            self._msg_struct = _make_msg_struct()
            hwnd = int(self.winId())
            ok = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(hwnd, 0)
            self._wts_registered = bool(ok)
        except Exception:
            self._wts_registered = False

    def _unregister_session_notification(self) -> None:
        if not self._wts_registered:
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(hwnd)
        except Exception:
            pass
        self._wts_registered = False

    def _handle_lock_state(self, locked: bool) -> None:
        if locked and not self._was_locked:
            self._was_locked = True
            self._was_visible_pre_lock = self.isVisible()
            if self.is_chat_open:
                self._toggle_chat()
            self.bubble.hide()
            self.hide()
            self.voice.stop()
        elif not locked and self._was_locked:
            self._was_locked = False
            if self._was_visible_pre_lock:
                self.show()

    def nativeEvent(self, eventType, message):  # noqa: N802
        if (sys.platform == "win32" and self._msg_struct is not None
                and eventType in ("windows_generic_MSG", b"windows_generic_MSG")):
            try:
                m = self._msg_struct.from_address(int(message))
                if m.message == self._WM_WTSSESSION_CHANGE:
                    if m.wParam == self._WTS_SESSION_LOCK:
                        self._handle_lock_state(True)
                    elif m.wParam == self._WTS_SESSION_UNLOCK:
                        self._handle_lock_state(False)
            except Exception:
                pass
        # Don't chain to super() — QWidget.nativeEvent under PyQt6 6.11 +
        # Python 3.14 segfaults during early window-creation messages.
        return False, 0

    def closeEvent(self, ev):  # noqa: N802
        self._unregister_session_notification()
        super().closeEvent(ev)

    # -- multi-monitor / DPI changes --
    def _on_screen_changed(self, *_args) -> None:
        scr = self._qscreen.availableGeometry()
        self._screen = scr
        # clamp into the new geometry
        self.pos_x = max(scr.left(), min(self.pos_x, scr.right() - SPRITE_SIZE))
        self.pos_y = scr.bottom() - TASKBAR_OFFSET - SPRITE_SIZE
        self.move(int(self.pos_x), int(self.pos_y))
        # reload sprites if DPR changed (different scaling factor on this monitor)
        new_dpr = self._qscreen.devicePixelRatio() if self._qscreen else 1.0
        if abs(new_dpr - getattr(self, "_sprite_dpr", 1.0)) > 1e-6:
            try:
                self._load_sprites()
                self._render()
            except Exception:
                pass

    # -- mouse: click rocky toggles chat (drag suppression on tiny mouse moves) --
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            self._press_pos = ev.globalPosition().toPoint()
        elif ev.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(ev.globalPosition().toPoint())

    def _show_context_menu(self, global_pos: QPoint) -> None:
        m = QMenu(self)
        m.addAction("Show Chat", self.show_chat)
        m.addAction("Restart Claude", self.restart_claude)
        m.addSeparator()
        voice_label = f"Voice: {'On' if self.voice.enabled else 'Off'}"
        voice_action = m.addAction(voice_label)
        voice_action.setEnabled(bool(self.voice.by_category))
        voice_action.triggered.connect(self._toggle_voice)
        pause_action = m.addAction(f"Pause Walk: {'On' if self._paused else 'Off'}")
        pause_action.triggered.connect(lambda: self.set_paused(not self._paused))
        m.addSeparator()
        m.addAction("Hide Rocky", self.hide)
        m.addAction("Quit", QApplication.instance().quit)
        m.exec(global_pos)

    def _toggle_voice(self) -> None:
        on = self.voice.toggle()
        if hasattr(self, "_tray_voice_action") and self._tray_voice_action is not None:
            self._tray_voice_action.setText(f"Voice: {'On' if on else 'Off'}")

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        if ev.button() != Qt.MouseButton.LeftButton or self._press_pos is None:
            return
        moved = (ev.globalPosition().toPoint() - self._press_pos).manhattanLength()
        self._press_pos = None
        if moved > 6:
            return
        if self._health_active:
            self._ack_health_check()
            return
        self._toggle_chat()

    def _toggle_chat(self) -> None:
        if self.is_chat_open:
            self.chat.hide()
            self.is_chat_open = False
            # resume motion (unless user paused walking)
            if not self._paused:
                self.move_timer.start(MOVE_TICK_MS)
                self.walk_timer.start(WALK_FRAME_MS)
                self._schedule_idle()
        else:
            # anchor near rocky, above him; clamp into screen
            scr = self._screen
            cw, ch = self.chat.width(), self.chat.height()
            x = int(self.pos_x + SPRITE_SIZE / 2 - cw / 2)
            y = int(self.pos_y - ch - 8)
            x = max(scr.left() + 4, min(x, scr.right() - cw - 4))
            y = max(scr.top() + 4, y)
            self.chat.move(x, y)
            self.chat.show()
            self.chat.raise_()
            self.chat.input.setFocus()
            self.is_chat_open = True
            # pause motion + idle jazz while chatting (saves wakeups)
            self.move_timer.stop()
            self.walk_timer.stop()
            self.idle_timer.stop()
        self._render()


# -- reminders ----------------------------------------------------------------

class ReminderManager(QObject):
    """Watches REMINDERS_JSON, schedules QTimer fires, shows toast + voice on fire.

    MCP server appends entries to REMINDERS_JSON; QFileSystemWatcher picks up
    the change and we schedule any new ones. On launch, missed-by-<1h fire
    immediately; older ones drop. Single-process: rocky must be running.
    """

    GRACE_SEC = 3600  # missed-by < 1h fires immediately on relaunch

    fired = pyqtSignal(str, str)  # category="reminder", text — drives Rocky.show_health_check

    def __init__(self, voice: "VoicePack",
                 tray: QSystemTrayIcon | None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.voice = voice
        self.tray = tray
        self._scheduled: dict[str, tuple[QTimer, dict]] = {}
        REMINDERS_JSON.parent.mkdir(parents=True, exist_ok=True)
        if not REMINDERS_JSON.exists():
            REMINDERS_JSON.write_text("[]", "utf-8")
        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(str(REMINDERS_JSON))
        self._watcher.addPath(str(REMINDERS_JSON.parent))
        self._watcher.fileChanged.connect(self._on_file_change)
        self._watcher.directoryChanged.connect(self._on_dir_change)
        QTimer.singleShot(0, self._reload)

    def _on_file_change(self, _path: str) -> None:
        QTimer.singleShot(150, self._reload)

    def _on_dir_change(self, _path: str) -> None:
        # Dir watcher fires for any sibling write (audit.log etc.). Skip unless
        # reminders.json mtime actually moved.
        try:
            mtime = REMINDERS_JSON.stat().st_mtime_ns
        except Exception:
            return
        if getattr(self, "_last_mtime", 0) == mtime:
            return
        self._last_mtime = mtime
        QTimer.singleShot(150, self._reload)

    def _reload(self) -> None:
        # editors / atomic-rename can drop our watch; re-add defensively
        if str(REMINDERS_JSON) not in self._watcher.files():
            if REMINDERS_JSON.exists():
                self._watcher.addPath(str(REMINDERS_JSON))
        try:
            entries = json.loads(REMINDERS_JSON.read_text("utf-8"))
        except Exception:
            return
        now = datetime.now(timezone.utc)
        kept: list[dict] = []
        changed = False
        for e in entries:
            rid = e.get("id")
            if not rid:
                changed = True
                continue
            if rid in self._scheduled:
                kept.append(e)
                continue
            try:
                fire_at = datetime.fromisoformat(e["fire_at"])
                if fire_at.tzinfo is None:
                    fire_at = fire_at.replace(tzinfo=timezone.utc)
            except Exception:
                changed = True
                continue
            delta = (fire_at - now).total_seconds()
            if delta <= 0:
                if delta > -self.GRACE_SEC:
                    self._fire(e)
                changed = True
                continue
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda eid=rid: self._on_timer_due(eid))
            self._arm_timer(t, delta * 1000)
            self._scheduled[rid] = (t, e)
            kept.append(e)
        if changed:
            try:
                REMINDERS_JSON.write_text(json.dumps(kept, indent=2), "utf-8")
            except Exception:
                pass

    # QTimer interval is signed int32 ms (~24.8 days). Re-arm in chunks for
    # longer delays.
    TIMER_MAX_MS = 2_147_483_000

    def _arm_timer(self, t: QTimer, remaining_ms: float) -> None:
        ms = int(max(0, min(remaining_ms, self.TIMER_MAX_MS)))
        t.start(ms)

    def _on_timer_due(self, rid: str) -> None:
        pair = self._scheduled.get(rid)
        if pair is None:
            return
        t, entry = pair
        try:
            fire_at = datetime.fromisoformat(entry["fire_at"])
            if fire_at.tzinfo is None:
                fire_at = fire_at.replace(tzinfo=timezone.utc)
        except Exception:
            self._scheduled.pop(rid, None)
            return
        remaining = (fire_at - datetime.now(timezone.utc)).total_seconds() * 1000
        if remaining > 1000:  # still in the future — chain
            self._arm_timer(t, remaining)
            return
        self._fire_by_id(rid)

    def _fire_by_id(self, rid: str) -> None:
        pair = self._scheduled.pop(rid, None)
        if pair is None:
            return
        _, entry = pair
        self._fire(entry)
        try:
            entries = json.loads(REMINDERS_JSON.read_text("utf-8"))
            entries = [e for e in entries if e.get("id") != rid]
            REMINDERS_JSON.write_text(json.dumps(entries, indent=2), "utf-8")
        except Exception:
            pass

    def _fire(self, entry: dict) -> None:
        text = str(entry.get("text", "(reminder)"))
        ok = show_toast("rocky reminder", text)
        if not ok and self.tray is not None:
            try:
                self.tray.showMessage(
                    "rocky reminder", text,
                    QSystemTrayIcon.MessageIcon.Information, 5000,
                )
            except Exception:
                pass
        try:
            self.voice.play("session_start")
        except Exception:
            pass
        audit("reminder_fire", {"id": entry.get("id"), "text": text})
        self.fired.emit("reminder", text)


class HealthCheckManager(QObject):
    """Recurring local nudges (water / stretch / eyes / posture / mental).

    Distinct from ReminderManager: no MCP entry path, no JSON queue from Claude.
    Per-category interval + jitter, persisted to ~/.agentrocky/health.json.
    Quiet-hours window suppresses fires; missed fires while app off fire once
    on next launch (no backfill).
    """

    fired = pyqtSignal(str, str)  # category, text — drives Rocky.show_health_check

    def __init__(self, voice: "VoicePack", tray: QSystemTrayIcon | None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.voice = voice
        self.tray = tray
        self.config = self._load_or_init()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(HEALTH_TICK_MS)
        # live-reload health.json on external edits (mirror ReminderManager).
        # self-writes also trigger this; reload is idempotent (setdefault keys
        # already present) so no extra fires.
        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(str(HEALTH_JSON))
        self._watcher.addPath(str(HEALTH_JSON.parent))
        self._watcher.fileChanged.connect(self._on_file_change)
        self._watcher.directoryChanged.connect(self._on_dir_change)
        QTimer.singleShot(0, self._tick)  # immediate check on launch

    def _on_file_change(self, _path: str) -> None:
        QTimer.singleShot(150, self._reload)

    def _on_dir_change(self, _path: str) -> None:
        # Dir watcher fires for any sibling write. Skip unless health.json mtime moved.
        try:
            mtime = HEALTH_JSON.stat().st_mtime_ns
        except Exception:
            return
        if getattr(self, "_last_mtime", 0) == mtime:
            return
        self._last_mtime = mtime
        QTimer.singleShot(150, self._reload)

    def _reload(self) -> None:
        # editors / atomic-rename drop the watch; re-add defensively
        if str(HEALTH_JSON) not in self._watcher.files():
            if HEALTH_JSON.exists():
                self._watcher.addPath(str(HEALTH_JSON))
        try:
            cfg = json.loads(HEALTH_JSON.read_text("utf-8"))
            if isinstance(cfg, dict):
                self.config = cfg
        except Exception:
            pass

    def _load_or_init(self) -> dict:
        HEALTH_JSON.parent.mkdir(parents=True, exist_ok=True)
        cfg: dict | None = None
        if HEALTH_JSON.exists():
            try:
                cfg = json.loads(HEALTH_JSON.read_text("utf-8"))
            except Exception:
                cfg = None
        if not isinstance(cfg, dict):
            cfg = {}
        cfg.setdefault("enabled", True)
        # Quiet hours disabled by default — start == end short-circuits in
        # _in_quiet_hours. User opts in by editing health.json.
        cfg.setdefault("quiet_start", "00:00")
        cfg.setdefault("quiet_end", "00:00")
        cats = cfg.setdefault("categories", {})
        now = datetime.now().astimezone()
        for key, default in HEALTH_DEFAULT_CATS.items():
            entry = cats.setdefault(key, {})
            for k, v in default.items():
                entry.setdefault(k, v)
            if "next_fire_at" not in entry:
                entry["next_fire_at"] = self._roll_next(entry, now).isoformat()
        self._save(cfg)
        return cfg

    def _save(self, cfg: dict | None = None) -> None:
        try:
            HEALTH_JSON.write_text(
                json.dumps(cfg if cfg is not None else self.config, indent=2),
                "utf-8",
            )
        except Exception:
            pass

    def _roll_next(self, entry: dict, now: datetime) -> datetime:
        interval = max(1, int(entry.get("interval_min", 60)))
        jitter = max(0, int(entry.get("jitter_min", 0)))
        offset = interval * 60
        if jitter:
            offset += random.randint(-jitter * 60, jitter * 60)
        offset = max(60, offset)
        return now + timedelta(seconds=offset)

    @staticmethod
    def _parse_hhmm(s: str, fallback: tuple[int, int]) -> tuple[int, int]:
        try:
            h, m = s.split(":")
            return int(h), int(m)
        except Exception:
            return fallback

    def _in_quiet_hours(self, now: datetime) -> bool:
        qs_h, qs_m = self._parse_hhmm(self.config.get("quiet_start", "22:00"), (22, 0))
        qe_h, qe_m = self._parse_hhmm(self.config.get("quiet_end", "08:00"), (8, 0))
        cur = now.hour * 60 + now.minute
        start = qs_h * 60 + qs_m
        end = qe_h * 60 + qe_m
        if start == end:
            return False
        if start < end:
            return start <= cur < end
        return cur >= start or cur < end  # wraps midnight

    def _quiet_end_dt(self, now: datetime) -> datetime:
        qe_h, qe_m = self._parse_hhmm(self.config.get("quiet_end", "08:00"), (8, 0))
        candidate = now.replace(hour=qe_h, minute=qe_m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _tick(self) -> None:
        if not self.config.get("enabled"):
            return
        now = datetime.now().astimezone()
        in_quiet = self._in_quiet_hours(now)
        changed = False
        for key, entry in self.config.get("categories", {}).items():
            if not entry.get("enabled"):
                continue
            try:
                nxt = datetime.fromisoformat(entry.get("next_fire_at", ""))
                if nxt.tzinfo is None:
                    nxt = nxt.astimezone()
            except Exception:
                entry["next_fire_at"] = self._roll_next(entry, now).isoformat()
                changed = True
                continue
            if nxt > now:
                continue
            if in_quiet:
                entry["next_fire_at"] = self._quiet_end_dt(now).isoformat()
                changed = True
                continue
            self._fire(key, entry)
            entry["next_fire_at"] = self._roll_next(entry, now).isoformat()
            changed = True
        if changed:
            self._save()

    def _fire(self, category: str, entry: dict) -> None:
        text = str(entry.get("copy", f"rocky check: {category}"))
        ok = show_toast("rocky check", text)
        if not ok and self.tray is not None:
            try:
                self.tray.showMessage(
                    "rocky check", text,
                    QSystemTrayIcon.MessageIcon.Information, 5000,
                )
            except Exception:
                pass
        try:
            self.voice.play("input_required")
        except Exception:
            pass
        audit("health_fire", {"category": category, "text": text})
        self.fired.emit(category, text)

    def set_master(self, on: bool) -> None:
        self.config["enabled"] = bool(on)
        self._save()

    def set_category(self, key: str, on: bool) -> None:
        cat = self.config.get("categories", {}).get(key)
        if not cat:
            return
        cat["enabled"] = bool(on)
        if on:
            cat["next_fire_at"] = self._roll_next(
                cat, datetime.now().astimezone()
            ).isoformat()
        self._save()


def _attach_health_menu(tray: QSystemTrayIcon, health: HealthCheckManager) -> None:
    """Insert Health Check-ins submenu before Quit in the existing tray menu."""
    menu = tray.contextMenu()
    if menu is None:
        return
    quit_action = None
    for a in menu.actions():
        if a.text() == "Quit":
            quit_action = a
            break
    sep = menu.insertSeparator(quit_action) if quit_action else menu.addSeparator()

    submenu = QMenu("Health Check-ins")
    master = submenu.addAction("Master enable")
    master.setCheckable(True)
    master.setChecked(bool(health.config.get("enabled", True)))
    master.toggled.connect(health.set_master)
    submenu.addSeparator()
    for key in HEALTH_DEFAULT_CATS:
        cat = health.config.get("categories", {}).get(key, {})
        interval = int(cat.get("interval_min", 0))
        act = submenu.addAction(f"{key.capitalize()} ({interval}m)")
        act.setCheckable(True)
        act.setChecked(bool(cat.get("enabled", False)))
        act.toggled.connect(lambda on, k=key: health.set_category(k, on))
    submenu.addSeparator()
    submenu.addAction(
        "Edit health.json…",
        lambda: os.startfile(str(HEALTH_JSON)) if HEALTH_JSON.exists() else None,
    )
    submenu_action = menu.insertMenu(sep, submenu)
    # keep refs alive on the tray to prevent GC of submenu/actions
    tray._agentrocky_health_submenu = submenu
    tray._agentrocky_health_submenu_action = submenu_action


# -- main ---------------------------------------------------------------------

def _build_tray(app: QApplication, rocky: "Rocky") -> QSystemTrayIcon | None:
    """Tray icon with right-click menu. Returns None if unsupported."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    icon = QIcon(str(SPRITE_DIR / SPRITE_FILES["stand"]))
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("agentrocky — starting…")
    menu = QMenu()
    menu.addAction("Show Chat", rocky.show_chat)
    menu.addAction("Show Rocky", rocky.show)
    menu.addAction("Hide Rocky", rocky.hide)
    menu.addSeparator()
    menu.addAction("Restart Claude", rocky.restart_claude)
    menu.addAction("Open Workspace", lambda: os.startfile(str(WORKSPACE)))
    menu.addAction("Open Audit Log", lambda: os.startfile(str(AUDIT_LOG))
                   if AUDIT_LOG.exists() else None)
    menu.addAction("Open Crash Log", lambda: os.startfile(str(CRASH_LOG))
                   if CRASH_LOG.exists() else None)
    menu.addSeparator()
    voice_label = f"Voice: {'On' if rocky.voice.enabled else 'Off'}"
    voice_action = menu.addAction(voice_label)
    voice_action.setEnabled(bool(rocky.voice.by_category))
    voice_action.triggered.connect(rocky._toggle_voice)
    rocky._tray_voice_action = voice_action
    pause_action = menu.addAction("Pause Walk")
    pause_action.setCheckable(True)
    pause_action.setChecked(rocky._paused)
    pause_action.toggled.connect(rocky.set_paused)
    rocky._tray_pause_action = pause_action
    menu.addSeparator()
    quit_action = menu.addAction("Quit")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    # left-click toggles chat
    tray.activated.connect(lambda reason: (
        rocky.show_chat() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    ))
    tray.show()
    return tray


class _MSG(object):
    """Lightweight ctypes MSG view — only fields we read."""


def _make_msg_struct():
    import ctypes
    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("message", ctypes.c_uint),
            ("wParam", ctypes.c_ssize_t),
            ("lParam", ctypes.c_ssize_t),
            ("time", ctypes.c_uint),
            ("pt_x", ctypes.c_long),
            ("pt_y", ctypes.c_long),
        ]
    return MSG


_HOTKEY_ID = 0xB001
_WM_HOTKEY = 0x0312
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_NOREPEAT = 0x4000
_VK_R = 0x52


class GlobalHotkey(QObject, QAbstractNativeEventFilter):
    """Win32 RegisterHotKey wrapper. Emits `triggered` on Ctrl+Alt+R."""

    triggered = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._registered = False
        self._msg_struct = None

    def register(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            self._msg_struct = _make_msg_struct()
            ok = ctypes.windll.user32.RegisterHotKey(
                None, _HOTKEY_ID,
                _MOD_CONTROL | _MOD_ALT | _MOD_NOREPEAT, _VK_R,
            )
            self._registered = bool(ok)
        except Exception:
            self._registered = False
        return self._registered

    def unregister(self) -> None:
        if not self._registered:
            return
        try:
            import ctypes
            ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
        except Exception:
            pass
        self._registered = False

    def nativeEventFilter(self, eventType, message):  # noqa: N802
        if not self._registered or self._msg_struct is None:
            return False, 0
        try:
            if eventType in ("windows_generic_MSG", b"windows_generic_MSG"):
                msg = self._msg_struct.from_address(int(message))
                if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                    self.triggered.emit()
                    return True, 0
        except Exception:
            pass
        return False, 0


def _set_app_user_model_id() -> None:
    """Win32 AUMID — toasts + taskbar group under 'agentrocky', not 'python.exe'."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("agentrocky.app")
    except Exception:
        pass


def main() -> int:
    _set_app_user_model_id()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _install_excepthook()

    # single-instance lock (silent exit if already running)
    shm = QSharedMemory("agentrocky-singleton-v1")
    if not shm.create(1):
        return 0
    app._agentrocky_shm = shm  # keep reference alive

    # ensure sandbox workspace exists before launching claude
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        QMessageBox.critical(None, "agentrocky",
                             f"Cannot create workspace at {WORKSPACE}:\n{e}")
        return 1

    # write MCP config so claude can call rocky tools (reminder/note/open/launch)
    # frozen build → check sibling mcp_server.exe; source → check mcp_server.py
    mcp_available = (MCP_SERVER_EXE.exists() if getattr(sys, "frozen", False)
                     else MCP_SERVER_PY.exists())
    if mcp_available:
        try:
            _write_mcp_config()
        except Exception as e:
            print(f"warning: could not write MCP config: {e}", file=sys.stderr)

    missing = [f for f in SPRITE_FILES.values() if not (SPRITE_DIR / f).exists()]
    if missing:
        try:
            SPRITE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        box = QMessageBox(None)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("agentrocky")
        box.setText("Missing sprite files in ./sprites/:")
        box.setInformativeText(
            "  " + "\n  ".join(missing)
            + "\n\nCopy them from https://github.com/itmesneha/agentrocky "
              "(agentrocky/Assets.xcassets).\n\n"
              f"Sprite folder: {SPRITE_DIR}"
        )
        open_btn = box.addButton("Open Sprite Folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_btn:
            try:
                os.startfile(str(SPRITE_DIR))
            except Exception:
                pass
        return 1

    session = ClaudeSession()
    rocky = Rocky(session)
    rocky.show()

    tray = _build_tray(app, rocky)
    rocky._tray = tray  # let rocky update tooltip on ready
    app._agentrocky_tray = tray  # prevent GC

    # reminder scheduler — watches reminders.json, fires QTimer + toast + voice
    reminders = ReminderManager(rocky.voice, tray)
    reminders.fired.connect(rocky.show_health_check)
    app._agentrocky_reminders = reminders  # keep reference alive

    # health check-ins — recurring local nudges (water/stretch/eyes/etc.)
    health = HealthCheckManager(rocky.voice, tray)
    health.fired.connect(rocky.show_health_check)
    app._agentrocky_health = health
    if tray is not None:
        _attach_health_menu(tray, health)

    # global hotkey Ctrl+Alt+R → show chat (Win32 only)
    hotkey = GlobalHotkey()
    if hotkey.register():
        app.installNativeEventFilter(hotkey)
        hotkey.triggered.connect(rocky.show_chat)
        app.aboutToQuit.connect(hotkey.unregister)
    app._agentrocky_hotkey = hotkey  # keep reference alive

    # buffered audit log: 1s flush timer + final flush on quit
    audit_timer = QTimer()
    audit_timer.timeout.connect(flush_audit)
    audit_timer.start(1000)
    app._agentrocky_audit_timer = audit_timer  # keep reference alive

    # clean shutdown of claude subprocess + audio
    app.aboutToQuit.connect(session.stop)
    app.aboutToQuit.connect(rocky.voice.stop)
    app.aboutToQuit.connect(flush_audit)

    session.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
