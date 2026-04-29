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
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    import winsound
else:
    winsound = None  # type: ignore

from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QObject, pyqtSignal, QSize, QRectF, QSharedMemory,
    QElapsedTimer,
)
from PyQt6.QtGui import (
    QPixmap, QTransform, QPainter, QColor, QFont, QFontDatabase,
    QPainterPath, QPen, QBrush, QTextCursor, QIcon, QGuiApplication, QCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QMessageBox,
    QSystemTrayIcon, QMenu,
)


# -- constants ----------------------------------------------------------------

SPRITE_DIR = Path(__file__).parent / "sprites"
SOUND_DIR = Path(__file__).parent / "sounds"
SPRITE_FILES = {
    "stand": "stand.png",
    "walk1": "walkleft1.png",
    "walk2": "walkleft2.png",
    "jazz1": "jazz1.png",
    "jazz2": "jazz2.png",
    "jazz3": "jazz3.png",
}
SPRITE_SIZE = 96
WALK_SPEED_PX = 1.5            # per 16ms tick → ~90px/s
TASKBAR_OFFSET = 50            # gap above bottom of screen
JAZZ_DURATION_MS = 2400
JAZZ_FRAME_MS = 150
WALK_FRAME_MS = 125            # 8fps
MOVE_TICK_MS = 16              # 60fps
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


def _install_excepthook() -> None:
    """Route unhandled exceptions to ~/.agentrocky/log.txt + a dialog."""
    import traceback

    def hook(etype, value, tb):
        try:
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            with CRASH_LOG.open("a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now(timezone.utc).isoformat()} ---\n")
                traceback.print_exception(etype, value, tb, file=f)
        except Exception:
            pass
        try:
            QMessageBox.critical(
                None,
                "agentrocky crashed",
                f"Unhandled error: {etype.__name__}: {value}\n\nLog: {CRASH_LOG}",
            )
        except Exception:
            pass
        sys.__excepthook__(etype, value, tb)

    sys.excepthook = hook


def audit(kind: str, payload) -> None:
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "data": payload,
            }) + "\n")
    except Exception:
        pass  # never let logging break the app


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
                self.durations[f] = _wav_duration_ms(f)
        if not self.by_category:
            self.enabled = False

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
        self._busy_until_ms = now + self.durations.get(clip, 1500)
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

    def show_text(self, text: str, anchor_center_x: int, anchor_top_y: int) -> None:
        # debounce: drop if a bubble appeared too recently (prevents flicker on tool spam)
        if not hasattr(self, "_etimer"):
            self._etimer = QElapsedTimer()
            self._etimer.start()
        if self.isVisible() and self._etimer.elapsed() - self._last_shown_ms < BUBBLE_DEBOUNCE_MS:
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
        self._hide_timer.start(BUBBLE_HIDE_MS)

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


class HistoryLineEdit(QLineEdit):
    """QLineEdit with shell-style Up/Down history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._idx: int | None = None  # None = editing fresh line
        self._draft = ""

    def push(self, text: str) -> None:
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self._idx = None
        self._draft = ""

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if ev.key() == Qt.Key.Key_Up and self._history:
            if self._idx is None:
                self._draft = self.text()
                self._idx = len(self._history) - 1
            elif self._idx > 0:
                self._idx -= 1
            self.setText(self._history[self._idx])
            return
        if ev.key() == Qt.Key.Key_Down and self._idx is not None:
            if self._idx < len(self._history) - 1:
                self._idx += 1
                self.setText(self._history[self._idx])
            else:
                self._idx = None
                self.setText(self._draft)
            return
        super().keyPressEvent(ev)


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
            f"QLineEdit{{background:transparent;color:{COLOR_TEXT};border:none;}}"
        )
        self.input.returnPressed.connect(self._on_submit)
        bar_lay.addWidget(self.input, 1)
        root.addWidget(bar)

        # blink the cursor while running
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_state = True

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
        self.output.append(f'<span style="color:{color};">{safe}</span>')
        self.output.moveCursor(QTextCursor.MoveOperation.End)

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
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(SPRITE_SIZE, SPRITE_SIZE)

        self.session = session
        self.sprites: dict[str, QPixmap] = {}
        self._load_sprites()
        self.voice = VoicePack(SOUND_DIR)

        self.label = QLabel(self)
        self.label.resize(SPRITE_SIZE, SPRITE_SIZE)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

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

        # lock-screen detection (Win32 only) — poll every 3s
        self._was_locked = False
        self._was_visible_pre_lock = True
        if sys.platform == "win32":
            self.lock_timer = QTimer(self)
            self.lock_timer.timeout.connect(self._tick_lock_state)
            self.lock_timer.start(3000)

        self._render()

    def _load_sprites(self) -> None:
        # render at native pixel density so sprites stay crisp on 4K / 200% scaling
        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        target = max(1, int(round(SPRITE_SIZE * dpr)))
        for key, fname in SPRITE_FILES.items():
            path = SPRITE_DIR / fname
            pix = QPixmap(str(path))
            if pix.isNull():
                raise RuntimeError(f"failed to load sprite: {path}")
            scaled = pix.scaled(
                target, target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
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
        if self.is_chat_open or self.is_jazzing:
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
        if self.is_jazzing or self.is_chat_open:
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
        if not self.is_chat_open and not self.is_jazzing:
            self._start_jazz()
        self._schedule_idle()

    # -- bubble --
    def _show_bubble(self, text: str) -> None:
        cx = int(self.pos_x + SPRITE_SIZE / 2)
        top = int(self.pos_y) + 4
        self.bubble.show_text(text, cx, top)

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
        self._claude_ready = False
        if hasattr(self, "_tray") and self._tray is not None:
            self._tray.setToolTip("agentrocky — starting…")
        self.session.start()

    # -- lock screen --
    @staticmethod
    def _is_workstation_locked() -> bool:
        """True if Windows workstation is locked. Uses OpenInputDesktop heuristic."""
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            DESKTOP_SWITCHDESKTOP = 0x0100
            h = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
            if not h:
                return True
            user32.CloseDesktop(h)
            return False
        except Exception:
            return False

    def _tick_lock_state(self) -> None:
        locked = self._is_workstation_locked()
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

    # -- multi-monitor / DPI changes --
    def _on_screen_changed(self, *_args) -> None:
        scr = self._qscreen.availableGeometry()
        self._screen = scr
        # clamp into the new geometry
        self.pos_x = max(scr.left(), min(self.pos_x, scr.right() - SPRITE_SIZE))
        self.pos_y = scr.bottom() - TASKBAR_OFFSET - SPRITE_SIZE
        self.move(int(self.pos_x), int(self.pos_y))

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
        self._toggle_chat()

    def _toggle_chat(self) -> None:
        if self.is_chat_open:
            self.chat.hide()
            self.is_chat_open = False
            # resume motion
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
    menu.addSeparator()
    voice_label = f"Voice: {'On' if rocky.voice.enabled else 'Off'}"
    voice_action = menu.addAction(voice_label)
    voice_action.setEnabled(bool(rocky.voice.by_category))
    voice_action.triggered.connect(rocky._toggle_voice)
    rocky._tray_voice_action = voice_action
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


def main() -> int:
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

    missing = [f for f in SPRITE_FILES.values() if not (SPRITE_DIR / f).exists()]
    if missing:
        QMessageBox.critical(
            None, "agentrocky",
            "Missing sprite files in ./sprites/:\n  " + "\n  ".join(missing)
            + "\n\nCopy them from https://github.com/itmesneha/agentrocky "
              "(agentrocky/Assets.xcassets).",
        )
        return 1

    session = ClaudeSession()
    rocky = Rocky(session)
    rocky.show()

    tray = _build_tray(app, rocky)
    rocky._tray = tray  # let rocky update tooltip on ready
    app._agentrocky_tray = tray  # prevent GC

    # clean shutdown of claude subprocess + audio
    app.aboutToQuit.connect(session.stop)
    app.aboutToQuit.connect(rocky.voice.stop)

    session.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
