from __future__ import annotations

import chess
from PyQt6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import config
import theme
from board_view import BoardView
from engine_worker import AnalysisResult, EngineWorker
from session import Session

CARD_RADIUS = 12
HEADER_HEIGHT = 38
HEADER_HEIGHT_COMPACT = 26
GRIP_SIZE = 14
AUTO_ACCEPT_DELAY_MS = 320

class CardHeader(QWidget):
    def __init__(self, window: "FloatWindow") -> None:
        super().__init__(window)
        self._window = window
        self._drag: QPoint | None = None
        self.setFixedHeight(HEADER_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(8)

        self.title = QLabel("ChessFloat")
        self.title.setObjectName("Title")
        self.status = QLabel("")
        self.status.setObjectName("Status")
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.eval = QLabel("—")
        self.eval.setObjectName("Eval")
        self.eval.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.eval.setFixedWidth(52)

        self.btn_auto = self._tool(
            "A",
            "自动采纳：引擎给出建议后自动走子\n（再点一次关闭；撤销/回退会自动暂停）",
            checkable=True,
        )
        self.btn_auto.setChecked(bool(window.cfg.get("auto_accept", False)))
        self.btn_pin = self._tool("⇧", "置顶（始终显示在最前）", checkable=True)
        self.btn_pin.setChecked(True)
        self.btn_settings = self._tool("⚙", "设置")
        self.btn_compact = self._tool("⊟", "紧凑模式（只留棋盘）")
        self.btn_close = self._tool("✕", "退出")

        row.addWidget(self.title)
        row.addWidget(self.status, 1)
        row.addWidget(self.eval)
        row.addWidget(self.btn_auto)
        row.addWidget(self.btn_pin)
        row.addWidget(self.btn_settings)
        row.addWidget(self.btn_compact)
        row.addWidget(self.btn_close)

    def _tool(self, text: str, tip: str, checkable: bool = False) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCheckable(checkable)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(24, 24)
        return btn

    def set_status(self, text: str, warn: bool = False) -> None:
        self.status.setText(text)
        self.status.setStyleSheet("color:#f87171;" if warn else "")

    def set_eval(self, text: str) -> None:
        self.eval.setText(text)

    def set_compact(self, compact: bool) -> None:
        self.title.setVisible(not compact)
        self.eval.setVisible(not compact)
        self.btn_auto.setVisible(not compact)
        self.btn_pin.setVisible(not compact)
        self.btn_settings.setVisible(not compact)
        self.setFixedHeight(HEADER_HEIGHT_COMPACT if compact else HEADER_HEIGHT)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._window.toggle_compact()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = CARD_RADIUS
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + radius)
        path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
        path.lineTo(rect.right() - radius, rect.top())
        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        painter.fillPath(path, theme.HEADER_BG)

class CardFooter(QWidget):
    def __init__(self, window: "FloatWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setFixedHeight(36)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 10, 6)
        row.setSpacing(6)

        self.btn_icon = QToolButton(self)
        self.btn_icon.setText("◐")
        self.btn_icon.setToolTip("透明度：无级拖动滑块 / Ctrl+滚轮 / ↑↓\n点此复位为默认")
        self.btn_icon.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_icon.setFixedSize(20, 22)
        self.btn_icon.setStyleSheet(
            "QToolButton{color:#8b95a9;border:none;background:transparent;font-size:12px;}"
            "QToolButton:hover{color:#dfe6f2;}"
        )

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(config.MIN_OPACITY * 100), int(config.MAX_OPACITY * 100))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)
        self.slider.setTracking(True)
        self.slider.setValue(int(round(window.cfg["opacity"] * 100)))
        self.slider.setFixedWidth(92)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setToolTip(
            f"浮窗透明度 {int(config.MIN_OPACITY * 100)}%–100%（1% 无级可调）\n"
            "也可以 Ctrl+滚轮 或 ↑/↓ 微调"
        )

        self.pct = QLabel(f"{self.slider.value()}%")
        self.pct.setObjectName("Pct")
        self.pct.setFixedWidth(32)
        self.pct.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.btn_accept = QPushButton("采纳")
        self.btn_accept.setObjectName("Primary")
        self.btn_accept.setToolTip("采纳引擎建议（空格）")
        self.btn_accept.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_accept.setFixedHeight(24)
        self.btn_accept.setMinimumWidth(52)

        self.btn_undo = self._tool("↩", "撤销一步（Ctrl+Z，长按连续撤销）")
        self.btn_redo = self._tool("↪", "重做（Ctrl+Y）")
        self.btn_flip = self._tool("⇅", "翻转视角（F）")
        self.btn_new = self._tool("⟳", "新开一局（N）")

        row.addWidget(self.btn_icon)
        row.addWidget(self.slider)
        row.addWidget(self.pct)
        row.addStretch(1)
        row.addWidget(self.btn_accept)
        row.addWidget(self.btn_undo)
        row.addWidget(self.btn_redo)
        row.addWidget(self.btn_flip)
        row.addWidget(self.btn_new)

    def set_opacity_text(self, value: int) -> None:
        self.pct.setText(f"{value}%")

    def _tool(self, text: str, tip: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(26, 24)
        return btn

class HistoryStrip(QWidget):

    jumped = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sans: list[str] = []
        self._ply = 0
        self._offset = 0.0
        self._chips: list[tuple[QRectF, int]] = []
        self._hover: int | None = None
        self._font = QFont(theme.UI_FONT)
        self._font.setPixelSize(11)

    def set_data(self, sans: list[str], ply: int) -> None:
        grew = len(sans) > len(self._sans)
        self._sans = list(sans)
        self._ply = ply
        if grew:
            self._offset = 1e9
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._font)
        metrics = QFontMetricsF(self._font)

        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.drawLine(0, 0, self.width(), 0)

        widths: list[float] = []
        for i, san in enumerate(self._sans):
            text = f"{i // 2 + 1}.{san}" if i % 2 == 0 else san
            widths.append(metrics.horizontalAdvance(text) + 12)
        total = sum(widths) + 12
        max_offset = max(0.0, total - self.width())
        self._offset = max(0.0, min(self._offset, max_offset))

        x = 10 - self._offset
        self._chips = []
        for i, san in enumerate(self._sans):
            text = f"{i // 2 + 1}.{san}" if i % 2 == 0 else san
            rect = QRectF(x, 3, widths[i], self.height() - 7)
            self._chips.append((rect, i))
            is_current = i == self._ply - 1
            if is_current:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(74, 222, 128, 46))
                painter.drawRoundedRect(rect, 4, 4)
            elif self._hover == i:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 16))
                painter.drawRoundedRect(rect, 4, 4)
            if i < self._ply:
                color = QColor(226, 232, 242) if is_current else QColor(176, 184, 200)
            else:
                color = QColor(104, 112, 128)
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            x += widths[i]

        if not self._sans:
            painter.setPen(QColor(96, 104, 120))
            painter.drawText(
                QRectF(10, 0, self.width() - 20, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                "尚无着法",
            )

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        for rect, index in self._chips:
            if rect.contains(pos):
                self.jumped.emit(index + 1)
                return

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        hover = None
        for rect, index in self._chips:
            if rect.contains(pos):
                hover = index
                break
        if hover != self._hover:
            self._hover = hover
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover = None
        self.update()

    def wheelEvent(self, event) -> None:
        self._offset -= event.angleDelta().y() * 0.4
        self.update()

class SideOverlay(QWidget):
    chosen = pyqtSignal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.addStretch(1)

        self.title = QLabel("选择你执的一方")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color:#eef2f8; font-size:14px; font-weight:600;")
        self.hint = QLabel("之后只需复刻对手着法\n空格一键采纳引擎建议")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet("color:#9aa4b8; font-size:11px; line-height:150%;")

        btn_white = QPushButton("执白 · 先手")
        btn_white.setObjectName("Primary")
        btn_white.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_white.setMinimumHeight(34)
        btn_white.clicked.connect(lambda: self.chosen.emit(True))

        btn_black = QPushButton("执黑 · 后手")
        btn_black.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_black.setMinimumHeight(34)
        btn_black.clicked.connect(lambda: self.chosen.emit(False))

        outer.addWidget(self.title)
        outer.addSpacing(6)
        outer.addWidget(self.hint)
        outer.addSpacing(18)
        outer.addWidget(btn_white)
        outer.addSpacing(8)
        outer.addWidget(btn_black)
        outer.addStretch(1)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(9, 10, 14, 214))
        painter.drawRect(self.rect())

class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ChessFloat 设置")
        self.setStyleSheet(theme.QSS)
        self.setMinimumWidth(400)

        form = QFormLayout(self)
        form.setContentsMargins(16, 16, 16, 12)
        form.setSpacing(10)

        self.strength = QComboBox()
        for key, (label, ms, threads, hash_mb) in config.STRENGTH_PRESETS.items():
            self.strength.addItem(f"{label}（{ms / 1000:.1f}s · {threads} 线程 · {hash_mb}MB）", key)
        self.strength.addItem("自定义", config.CUSTOM_STRENGTH)
        current = str(cfg.get("strength") or "balanced")
        index = self.strength.findData(current)
        self.strength.setCurrentIndex(index if index >= 0 else 0)
        self.strength.setToolTip("档位越高引擎越强，但箭头来得越慢")

        self.adaptive = QCheckBox("自适应：难的局面多算、无脑局面少算")
        self.adaptive.setChecked(bool(cfg.get("adaptive", True)))
        self.adaptive.setToolTip("残局/战术局面自动加时，强制着法自动减时")

        self.analysis = QSpinBox()
        self.analysis.setRange(100, 30000)
        self.analysis.setSingleStep(100)
        self.analysis.setSuffix(" ms")
        self.analysis.setValue(int(cfg["analysis_ms"]))

        self.debounce = QSpinBox()
        self.debounce.setRange(0, 1500)
        self.debounce.setSingleStep(50)
        self.debounce.setSuffix(" ms")
        self.debounce.setValue(int(cfg["debounce_ms"]))

        self.threads = QSpinBox()
        self.threads.setRange(1, 32)
        self.threads.setValue(int(cfg["threads"]))
        self.threads.setToolTip("实测超过 8 线程基本不再涨深度，反而可能因搜索摊薄而降层")

        self.hash = QSpinBox()
        self.hash.setRange(16, 4096)
        self.hash.setToolTip("够用即可，256MB 已能覆盖整局；加大主要减少重复计算")
        self.hash.setSingleStep(16)
        self.hash.setSuffix(" MB")
        self.hash.setValue(int(cfg["hash_mb"]))

        self.coords = QCheckBox("在棋盘上显示坐标")
        self.coords.setChecked(bool(cfg.get("show_coords", True)))

        self.auto_accept = QCheckBox("自动采纳：引擎出建议后自动走子")
        self.auto_accept.setChecked(bool(cfg.get("auto_accept", False)))

        self.low_priority = QCheckBox("引擎低优先级（玩游戏时不抢 CPU）")
        self.low_priority.setChecked(bool(cfg.get("low_priority", True)))
        self.low_priority.setToolTip("没有竞争时不影响引擎速度，只在别人抢 CPU 时让路")

        engine_row = QWidget()
        engine_layout = QHBoxLayout(engine_row)
        engine_layout.setContentsMargins(0, 0, 0, 0)
        engine_layout.setSpacing(6)
        self.engine_path = QLineEdit(str(cfg.get("engine_path") or ""))
        self.engine_path.setPlaceholderText("留空则自动使用 engine\\stockfish.exe")
        browse = QPushButton("浏览…")
        browse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse.clicked.connect(self._browse)
        engine_layout.addWidget(self.engine_path, 1)
        engine_layout.addWidget(browse)

        form.addRow("引擎强度", self.strength)
        form.addRow("", self.adaptive)
        form.addRow("单次分析限时", self.analysis)
        for spin in (self.analysis, self.threads, self.hash):
            spin.valueChanged.connect(self._mark_custom)

        form.addRow("走子防抖", self.debounce)
        form.addRow("引擎线程数", self.threads)
        form.addRow("Hash 大小", self.hash)
        form.addRow("引擎路径", engine_row)
        form.addRow("", self.coords)
        form.addRow("", self.auto_accept)
        form.addRow("", self.low_priority)

        self.strength.currentIndexChanged.connect(self._on_strength_changed)
        self._apply_strength_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_strength_changed(self) -> None:
        key = self.strength.currentData()
        if key in config.STRENGTH_PRESETS:
            _, ms, threads, hash_mb = config.STRENGTH_PRESETS[key]
            for widget, value in (
                (self.analysis, ms),
                (self.threads, threads),
                (self.hash, hash_mb),
            ):
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)
        self._apply_strength_enabled()

    def _mark_custom(self) -> None:
        if self.strength.currentData() != config.CUSTOM_STRENGTH:
            self.strength.blockSignals(True)
            self.strength.setCurrentIndex(self.strength.count() - 1)
            self.strength.blockSignals(False)
            self._apply_strength_enabled()

    def _apply_strength_enabled(self) -> None:
        custom = self.strength.currentData() == config.CUSTOM_STRENGTH
        for widget in (self.analysis, self.threads, self.hash):
            widget.setEnabled(custom)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 Stockfish 可执行文件", "", "可执行文件 (*.exe);;所有文件 (*)")
        if path:
            self.engine_path.setText(path)

    def values(self) -> dict:
        return {
            "analysis_ms": self.analysis.value(),
            "debounce_ms": self.debounce.value(),
            "threads": self.threads.value(),
            "hash_mb": self.hash.value(),
            "show_coords": self.coords.isChecked(),
            "auto_accept": self.auto_accept.isChecked(),
            "adaptive": self.adaptive.isChecked(),
            "low_priority": self.low_priority.isChecked(),
            "strength": self.strength.currentData(),
            "engine_path": self.engine_path.text().strip(),
        }

class ResizeGrip(QWidget):

    def __init__(self, window: "FloatWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setFixedSize(GRIP_SIZE, GRIP_SIZE)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("拖动缩放")
        self._origin: QPoint | None = None
        self._size = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.globalPosition().toPoint()
            self._size = self._window.size()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None and self._size is not None:
            delta = event.globalPosition().toPoint() - self._origin
            self._window.resize(
                max(config.MIN_WIDTH, self._size.width() + delta.x()),
                max(config.MIN_HEIGHT, self._size.height() + delta.y()),
            )
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._origin = None
        self._size = None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(255, 255, 255, 46), 1.4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        for offset in (3.0, 6.5, 10.0):
            painter.drawLine(
                int(self.width() - offset), self.height() - 2,
                self.width() - 2, int(self.height() - offset),
            )

class FloatWindow(QWidget):
    def __init__(self, cfg: dict) -> None:
        super().__init__(None)
        self.cfg = cfg
        self.setWindowTitle("ChessFloat")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(theme.QSS)
        self.setMinimumSize(config.MIN_WIDTH, config.MIN_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.session = Session(self)
        self._engine: EngineWorker | None = None
        self._engine_name = ""
        self._engine_ok = False
        self._engine_error: str | None = None
        self._suggestion: AnalysisResult | None = None
        self._last_cp: int | None = None
        self._last_eval_delta: float | None = None
        self._side_chosen = False
        self._thinking = False
        self._status_override: str | None = None
        self._status_warn = False
        self._compact = False
        self._normal_height = 620

        self.header = CardHeader(self)
        self.board = BoardView(self.session, self)
        self.board.show_coords = bool(cfg.get("show_coords", True))
        self.footer = CardFooter(self)
        self.history = HistoryStrip(self)
        self.overlay = SideOverlay(self.board)
        self.grip = ResizeGrip(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.board, 1)
        layout.addWidget(self.history)
        layout.addWidget(self.footer)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._start_analysis)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status_override)
        self._repeat_timer = QTimer(self)
        self._repeat_timer.setInterval(110)
        self._repeat_timer.timeout.connect(self.undo)

        self._wire()
        self._restore_geometry()
        self.setWindowOpacity(float(cfg["opacity"]))
        self.board.installEventFilter(self)
        self.overlay.setGeometry(self.board.rect())
        self.overlay.raise_()

        self._start_engine()
        self._refresh_ui()

    def _wire(self) -> None:
        self.session.positionChanged.connect(self._on_position_changed)
        self.session.historyChanged.connect(self._on_history_changed)

        self.board.movePlayed.connect(self._play_move)
        self.board.illegalMove.connect(lambda text: self._flash_status(text, warn=True))
        self.board.selectionChanged.connect(self._refresh_ui)

        self.header.btn_auto.toggled.connect(self._set_auto_accept)
        self.header.btn_pin.toggled.connect(self._set_always_on_top)
        self.header.btn_settings.clicked.connect(self.open_settings)
        self.header.btn_compact.clicked.connect(self.toggle_compact)
        self.header.btn_close.clicked.connect(self.close)

        self.footer.slider.valueChanged.connect(self._on_opacity)
        self.footer.btn_icon.clicked.connect(self.reset_opacity)
        self.footer.btn_accept.clicked.connect(self.accept_suggestion)
        self.footer.btn_undo.pressed.connect(self._begin_repeat_undo)
        self.footer.btn_undo.released.connect(self._repeat_timer.stop)
        self.footer.btn_redo.clicked.connect(self.redo)
        self.footer.btn_flip.clicked.connect(self.flip)
        self.footer.btn_new.clicked.connect(self.new_game)

        self.history.jumped.connect(self.jump_to)
        self.overlay.chosen.connect(self.choose_side)

    def eventFilter(self, obj, event):
        if obj is self.board and event.type() == QEvent.Type.Resize:
            self.overlay.setGeometry(self.board.rect())
        elif obj is self.board and event.type() == QEvent.Type.Wheel:

            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta:
                    self._adjust_opacity(2 if delta > 0 else -2)
                    return True
        return super().eventFilter(obj, event)

    def _start_engine(self) -> None:
        explicit = self.cfg.get("engine_path") or None
        path = config.find_engine(explicit)
        if path is None:
            self._engine_ok = False
            self._engine_error = "未找到 Stockfish，请把 stockfish.exe 放到 engine\\ 目录"
            self._status_override = None
            self._status_timer.stop()
            self.header.set_status(self._engine_error, warn=True)
            return
        self._engine_error = None
        self.cfg["engine_path"] = str(path)
        self._engine = EngineWorker(
            str(path),
            int(self.cfg["threads"]),
            int(self.cfg["hash_mb"]),
            bool(self.cfg.get("low_priority", True)),
        )
        self._engine.ready.connect(self._on_engine_ready)
        self._engine.failed.connect(self._on_engine_failed)
        self._engine.progress.connect(self._on_engine_progress)
        self._engine.analysisDone.connect(self._on_analysis_done)
        self._engine.start()

    def _stop_engine(self) -> None:
        if self._engine is not None:
            self._engine.shutdown()
            self._engine.wait(3000)
            self._engine = None
        self._engine_ok = False

    def _on_engine_ready(self, name: str) -> None:
        self._engine_ok = True
        self._engine_error = None
        self._engine_name = name
        self._flash_status(f"{name} 就绪")
        if self._side_chosen:
            self._schedule_analysis()

    def _on_engine_failed(self, message: str) -> None:
        self._engine_ok = False
        self._engine_error = message
        self.header.set_status(message, warn=True)

    def _on_engine_progress(self, data: dict) -> None:
        if data.get("version") != self.session.version:
            return
        self.header.set_eval(self.session.eval_text(data.get("cp"), data.get("mate")))
        if self._thinking and self._status_override is None:
            depth = data.get("depth") or 0
            self._set_status_quiet(f"分析中 · 深度 {depth}")

    def _on_analysis_done(self, result: AnalysisResult) -> None:
        if result.version != self.session.version:
            return
        self._thinking = False

        if not self.session.is_my_turn:
            self._refresh_ui()
            return

        if not result.uci:
            self._refresh_ui()
            return
        try:
            move = chess.Move.from_uci(result.uci)
        except ValueError:
            self._refresh_ui()
            return
        if move not in self.session.board.legal_moves:
            self._refresh_ui()
            return

        self._suggestion = result
        self.board.set_suggestion(move, stale=False)
        self.header.set_eval(self.session.eval_text(result.cp, result.mate))
        self._track_eval(result)
        self._refresh_ui()

        if self.cfg.get("auto_accept"):
            version = result.version
            QTimer.singleShot(
                AUTO_ACCEPT_DELAY_MS,
                lambda: self._auto_accept(version, move, result.san),
            )

    def _track_eval(self, result: AnalysisResult) -> None:

        if result.mate is not None:
            self._last_eval_delta = None
            self._last_cp = None
            return
        cp = result.cp or 0
        if self._last_cp is not None:
            self._last_eval_delta = abs(cp - self._last_cp) / 100.0
        self._last_cp = cp

    def _auto_accept(self, version: int, move: chess.Move, san: str) -> None:
        if not self.cfg.get("auto_accept"):
            return
        if version != self.session.version:
            return
        if self.board.is_interacting():
            return
        if move not in self.session.board.legal_moves:
            return
        if self._play_move(move):
            self._flash_status(f"自动采纳 {san}")

    def _schedule_analysis(self) -> None:
        self._debounce.stop()
        if not self._side_chosen:
            return
        if self.session.board.is_game_over():
            self._set_status_quiet("对局结束")
            return
        if not self.session.is_my_turn:

            return
        self._debounce.start(int(self.cfg["debounce_ms"]))

    def _start_analysis(self) -> None:
        if not self._side_chosen or self._engine is None or not self._engine_ok:
            return
        if self.session.board.is_game_over():
            return
        if not self.session.is_my_turn:
            return
        self._thinking = True
        movetime = self._movetime_for(self.session.board)
        self._engine.submit(
            self.session.version,
            self.session.board,
            movetime,
        )
        self._set_status_quiet(f"分析中… {movetime / 1000:.1f}s")

    def _movetime_for(self, board: chess.Board) -> int:

        base = int(self.cfg["analysis_ms"])
        if not self.cfg.get("adaptive", True):
            return base
        return int(max(500, min(30000, base * self._complexity_factor(board))))

    def _complexity_factor(self, board: chess.Board) -> float:

        factor = 1.0
        try:
            moves = board.legal_moves.count()
        except Exception:
            moves = 30
        pieces = len(board.piece_map())

        if pieces <= 10:
            factor += 0.60
        elif pieces <= 16:
            factor += 0.25
        if moves <= 3 and pieces > 10:
            factor -= 0.35
        if board.is_check():
            factor += 0.30
        if moves >= 35:
            factor += 0.25
        delta = self._last_eval_delta
        if delta is not None and delta > 1.0:
            factor += 0.40
        return max(0.4, min(2.5, factor))

    def _play_move(self, move: chess.Move) -> bool:
        if not self.session.push(move):
            self._flash_status("非法着法", warn=True)
            return False
        return True

    def _current_suggestion_move(self) -> chess.Move | None:

        board = self.session.board
        result = self._suggestion
        if result is not None and result.version == self.session.version:
            try:
                move = chess.Move.from_uci(result.uci)
            except ValueError:
                move = None
            if move is not None and move in board.legal_moves:
                return move
        arrow = self.board.suggestion_move
        if arrow is not None and arrow in board.legal_moves:
            return arrow
        return None

    def accept_suggestion(self) -> None:

        move = self._current_suggestion_move()
        if move is None:
            if self.board.suggestion_move is not None:
                self._flash_status("箭头是上一轮的建议，已失效", warn=True)
            else:
                self._flash_status("暂无可用建议", warn=True)
            return
        san = self.session.board.san(move)
        self._play_move(move)
        self._flash_status(f"已采纳 {san}")

    def undo(self) -> None:
        if not self.session.undo():
            return
        if self.cfg.get("auto_accept"):
            self._pause_auto_accept("已撤销一步")
        else:
            self._flash_status("已撤销一步")

    def redo(self) -> None:
        if not self.session.redo():
            return
        if self.cfg.get("auto_accept"):
            self._pause_auto_accept("已重做")
        else:
            self._flash_status("已重做")

    def jump_to(self, ply: int) -> None:
        if not self.session.jump_to(ply):
            return
        if self.cfg.get("auto_accept"):
            self._pause_auto_accept(f"回到第 {ply} 步")
        else:
            self._flash_status(f"回到第 {ply} 步")

    def flip(self) -> None:
        self.session.toggle_flip()

    def new_game(self) -> None:
        self._side_chosen = False
        self._suggestion = None
        self._last_cp = None
        self._last_eval_delta = None
        self.board.set_suggestion(None)
        self.session.reset(self.session.my_color)
        self.overlay.show()
        self.overlay.raise_()
        self._refresh_ui()

    def choose_side(self, is_white: bool) -> None:
        self.overlay.hide()
        self._side_chosen = True
        color = chess.WHITE if is_white else chess.BLACK
        self.session.my_color = color
        self.session.flipped = not is_white
        self.session.reset(color)
        self._refresh_ui()

    def _on_position_changed(self, version: int) -> None:
        prev = self.board.suggestion_move
        self._suggestion = None
        self._thinking = False
        if self._engine is not None:
            self._engine.cancel()

        if prev is None:
            self.board.set_suggestion(None)
        else:
            legal = prev in self.session.board.legal_moves
            self.board.set_suggestion(prev, stale=not (legal and self.session.is_my_turn))

        self._schedule_analysis()
        self._refresh_ui()

    def _on_history_changed(self) -> None:
        self.board.update()
        self.history.set_data(self.session.san_list(), self.session.ply)
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        board = self.session.board
        can_undo = self.session.ply > 0
        self.footer.btn_undo.setEnabled(can_undo)
        self.footer.btn_redo.setEnabled(self.session.can_redo)
        arrow = self.board.suggestion_move
        can_accept = self._suggestion is not None or (
            arrow is not None and arrow in board.legal_moves
        )
        self.footer.btn_accept.setEnabled(can_accept)

        if board.is_game_over():
            outcome = board.outcome()
            text = "对局结束"
            if outcome is not None and outcome.winner is not None:
                text = "白胜" if outcome.winner == chess.WHITE else "黑胜"
            self._set_status_quiet(text)
            return

        if not self._side_chosen:
            if self._engine_error:
                self.header.set_status(self._engine_error, warn=True)
            else:
                self.header.set_status("请选择先后手")
            self.header.set_eval("—")
            return

        if self._engine_error:

            self.header.set_status(self._engine_error, warn=True)
            self.header.set_eval("—")
            return

        if self._status_override:
            self.header.set_status(self._status_override, self._status_warn)
            return

        turn = self.session.turn_name
        if self.session.is_my_turn:
            if self._thinking:
                self._set_status_quiet(f"轮你走 · 分析中…")
            elif self._suggestion is not None:
                self._set_status_quiet(
                    f"轮你走 · 建议 {self._suggestion.san} · 深度 {self._suggestion.depth}"
                )
            else:
                self._set_status_quiet(f"轮你走 · {turn}")
        else:
            self._set_status_quiet(f"轮对手走 · 复刻对手着法")

    def _set_status_quiet(self, text: str) -> None:
        self.header.set_status(text)

    def _flash_status(self, text: str, warn: bool = False, ms: int = 1800) -> None:
        self._status_override = text
        self._status_warn = warn
        self.header.set_status(text, warn)
        self._status_timer.start(ms)

    def _clear_status_override(self) -> None:
        self._status_override = None
        self._status_warn = False
        self._refresh_ui()

    def _on_opacity(self, value: int) -> None:
        opacity = max(config.MIN_OPACITY, min(config.MAX_OPACITY, value / 100.0))
        self.cfg["opacity"] = round(opacity, 3)
        self.setWindowOpacity(opacity)
        self.footer.set_opacity_text(value)

    def _adjust_opacity(self, delta: int) -> None:

        value = self.footer.slider.value() + delta
        low = int(round(config.MIN_OPACITY * 100))
        high = int(round(config.MAX_OPACITY * 100))
        self.footer.slider.setValue(max(low, min(high, value)))

    def reset_opacity(self) -> None:
        self.footer.slider.setValue(int(round(config.DEFAULT_OPACITY * 100)))
        self._flash_status(f"透明度复位为 {int(round(config.DEFAULT_OPACITY * 100))}%")

    def wheelEvent(self, event) -> None:

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self._adjust_opacity(2 if delta > 0 else -2)
                event.accept()
                return
        super().wheelEvent(event)

    def _set_auto_accept(self, on: bool) -> None:
        self.cfg["auto_accept"] = bool(on)
        config.save_config(self.cfg)
        if not on:
            self._flash_status("自动采纳已关闭")
            return
        self._flash_status("自动采纳已开启")

        move = self._current_suggestion_move()
        if move is not None:
            version = self.session.version
            san = self.session.board.san(move)
            QTimer.singleShot(
                AUTO_ACCEPT_DELAY_MS,
                lambda: self._auto_accept(version, move, san),
            )

    def _pause_auto_accept(self, reason: str) -> None:

        if not self.cfg.get("auto_accept"):
            return
        self.header.btn_auto.blockSignals(True)
        self.header.btn_auto.setChecked(False)
        self.header.btn_auto.blockSignals(False)
        self.cfg["auto_accept"] = False
        config.save_config(self.cfg)
        self._flash_status(f"{reason} · 自动采纳已暂停")

    def _set_always_on_top(self, on: bool) -> None:
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def toggle_compact(self) -> None:
        self._compact = not self._compact
        if self._compact:
            self._normal_height = self.height()
            self.footer.setVisible(False)
            self.history.setVisible(False)
            self.header.set_compact(True)
            self.resize(self.width(), self.width() + HEADER_HEIGHT_COMPACT + 4)
        else:
            self.footer.setVisible(True)
            self.history.setVisible(True)
            self.header.set_compact(False)
            self.resize(self.width(), max(self._normal_height, self.width() + 80))
        self.header.btn_compact.setToolTip(
            "退出紧凑模式" if self._compact else "紧凑模式（只留棋盘）"
        )

    def set_strength(self, name: str) -> None:

        if name not in config.STRENGTH_PRESETS:
            return
        old = (self.cfg.get("threads"), self.cfg.get("hash_mb"))
        config.apply_preset(self.cfg, name)
        config.save_config(self.cfg)
        label = config.STRENGTH_PRESETS[name][0]
        if (self.cfg["threads"], self.cfg["hash_mb"]) != old:
            self._stop_engine()
            self._start_engine()
        else:
            self._schedule_analysis()
        self._flash_status(
            f"引擎强度：{label}（{int(self.cfg['analysis_ms']) / 1000:.1f}s · "
            f"{self.cfg['threads']} 线程 · {self.cfg['hash_mb']}MB）"
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.cfg, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        old = (
            self.cfg.get("engine_path"),
            self.cfg.get("threads"),
            self.cfg.get("hash_mb"),
            self.cfg.get("low_priority"),
        )
        self.cfg.update(values)
        self.header.btn_auto.blockSignals(True)
        self.header.btn_auto.setChecked(bool(values["auto_accept"]))
        self.header.btn_auto.blockSignals(False)
        self.board.show_coords = bool(values["show_coords"])
        self.board.update()
        new = (
            self.cfg.get("engine_path"),
            self.cfg.get("threads"),
            self.cfg.get("hash_mb"),
            self.cfg.get("low_priority"),
        )
        if new != old:
            self._stop_engine()
            self._start_engine()
        else:
            self._schedule_analysis()
        config.save_config(self.cfg)
        self._flash_status("设置已保存")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)

        if key == Qt.Key.Key_Space:
            self.accept_suggestion()
        elif key == Qt.Key.Key_Escape:
            self.board.clear_selection()
        elif ctrl and key == Qt.Key.Key_Z:
            self.undo()
        elif ctrl and key == Qt.Key.Key_Y:
            self.redo()
        elif ctrl and int(Qt.Key.Key_1) <= key <= int(Qt.Key.Key_4):
            names = list(config.STRENGTH_PRESETS)
            self.set_strength(names[key - int(Qt.Key.Key_1)])
        elif key == Qt.Key.Key_F:
            self.flip()
        elif key == Qt.Key.Key_N:
            self.new_game()
        elif key == Qt.Key.Key_Up:
            self._adjust_opacity(2)
        elif key == Qt.Key.Key_Down:
            self._adjust_opacity(-2)
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.grip.move(self.width() - GRIP_SIZE - 1, self.height() - GRIP_SIZE - 1)
        self.grip.raise_()

    def _begin_repeat_undo(self) -> None:

        self.undo()
        self._repeat_timer.start()

    def _restore_geometry(self) -> None:
        geo = self.cfg.get("geometry")
        screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else None
        if isinstance(geo, list) and len(geo) == 4:
            x, y, w, h = (int(v) for v in geo)
            w = max(config.MIN_WIDTH, w)
            h = max(config.MIN_HEIGHT, h)
            if area is not None:
                x = max(area.left(), min(x, area.right() - 80))
                y = max(area.top(), min(y, area.bottom() - 60))
            self.setGeometry(x, y, w, h)
        else:
            x, y, w, h = config.DEFAULT_GEOMETRY
            if area is not None:
                x = min(x, area.right() - w - 20)
                y = min(y, area.bottom() - h - 20)
            self.setGeometry(x, y, w, h)
        self._normal_height = self.height()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
        painter.fillPath(path, theme.CARD_BG)
        painter.setPen(QPen(theme.CARD_BORDER, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.overlay.setGeometry(self.board.rect())
        self.overlay.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def closeEvent(self, event) -> None:
        geo = self.geometry()
        self.cfg["geometry"] = [geo.x(), geo.y(), geo.width(), geo.height()]
        config.save_config(self.cfg)
        self._debounce.stop()
        self._stop_engine()
        super().closeEvent(event)
