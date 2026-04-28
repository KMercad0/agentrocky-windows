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
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QObject, pyqtSignal, QSize, QRectF,
)
from PyQt6.QtGui import (
    QPixmap, QTransform, QPainter, QColor, QFont, QFontDatabase,
    QPainterPath, QPen, QBrush, QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QMessageBox,
)


# -- constants ----------------------------------------------------------------

SPRITE_DIR = Path(__file__).parent / "sprites"
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


# -- claude subprocess --------------------------------------------------------

class ClaudeSession(QObject):
    """Persistent `claude` CLI subprocess in stream-json mode.

    Reader threads emit signals only — never touch widgets directly.
    """

    line_received = pyqtSignal(str, str)   # (text, kind: text|tool|system|error)
    task_complete = pyqtSignal()
    tool_use_seen = pyqtSignal(str)        # tool name
    ready = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.proc: subprocess.Popen | None = None
        self._stdin_lock = threading.Lock()

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
                cwd=str(Path.home()),
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
        self.line_received.emit("[claude process exited]", "system")

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
            return
        if t == "result":
            self.task_complete.emit()
            return

    def send(self, prompt: str) -> None:
        if not self.proc or not self.proc.stdin:
            return
        envelope = {
            "type": "user",
            "message": {"role": "user", "content": prompt},
        }
        data = json.dumps(envelope) + "\n"
        with self._stdin_lock:
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except Exception as e:
                self.line_received.emit(f"send failed: {e}", "error")


# -- speech bubble ------------------------------------------------------------

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
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, anchor_center_x: int, anchor_top_y: int) -> None:
        self._text = text
        # measure
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(text) + 24
        h = fm.height() + 18 + 8  # padding + tail
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
        # tail
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
        p.drawText(body, Qt.AlignmentFlag.AlignCenter, self._text)


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
        root.addWidget(self.output, 1)

        bar = QWidget()
        bar.setStyleSheet("background:#000;")
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(10, 6, 10, 8)
        prompt = QLabel("❯")
        prompt.setFont(mono_font(12))
        prompt.setStyleSheet(f"color:{COLOR_TEXT};")
        bar_lay.addWidget(prompt)
        self.input = QLineEdit()
        self.input.setFont(mono_font(11))
        self.input.setStyleSheet(
            f"QLineEdit{{background:transparent;color:{COLOR_TEXT};border:none;}}"
        )
        self.input.returnPressed.connect(self._on_submit)
        bar_lay.addWidget(self.input, 1)
        root.addWidget(bar)

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
            box.setWindowTitle("Heads up")
            box.setText(
                "Rocky runs claude with --dangerously-skip-permissions.\n\n"
                "Claude will execute tools (file edits, shell commands, etc.) "
                "WITHOUT asking each time. Only proceed if you understand the risk."
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            if box.exec() != QMessageBox.StandardButton.Ok:
                return
            self._opted_in = True
        self.input.clear()
        self.append_line(f"❯ {text}", "system")
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

        self.label = QLabel(self)
        self.label.resize(SPRITE_SIZE, SPRITE_SIZE)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # state
        scr = QApplication.primaryScreen().availableGeometry()
        self._screen = scr
        self.pos_x = float(scr.left() + scr.width() // 3)
        self.pos_y = scr.bottom() - TASKBAR_OFFSET - SPRITE_SIZE
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
        session.ready.connect(lambda: self.chat.append_line(
            "[claude ready]", "system"))

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

        self._render()

    def _load_sprites(self) -> None:
        for key, fname in SPRITE_FILES.items():
            path = SPRITE_DIR / fname
            pix = QPixmap(str(path))
            if pix.isNull():
                raise RuntimeError(f"failed to load sprite: {path}")
            self.sprites[key] = pix.scaled(
                SPRITE_SIZE, SPRITE_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    # -- rendering --
    def _current_pixmap(self) -> QPixmap:
        if self.is_jazzing:
            base = self.sprites[f"jazz{(self.jazz_frame % 3) + 1}"]
        elif self.is_chat_open:
            base = self.sprites["stand"]
        else:
            base = self.sprites["walk1" if self.walk_frame == 0 else "walk2"]
        # sprites face left; flip when moving right
        if self.direction > 0 and not self.is_chat_open:
            return base.transformed(QTransform().scale(-1, 1))
        return base

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

    # -- session events --
    def _on_task_complete(self) -> None:
        self._start_jazz()
        self._show_bubble(random.choice(DONE_BUBBLES))

    def _on_tool_use(self, _name: str) -> None:
        self._show_bubble(random.choice(TOOL_BUBBLES))

    def _on_user_send(self, text: str) -> None:
        self.session.send(text)

    # -- mouse: click rocky toggles chat (drag suppression on tiny mouse moves) --
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            self._press_pos = ev.globalPosition().toPoint()

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
        self._render()


# -- main ---------------------------------------------------------------------

def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

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
    session.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
