from __future__ import annotations

import math

import chess
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

import pieces
import theme
from session import Session

FILES = "abcdefgh"

class BoardView(QWidget):
    movePlayed = pyqtSignal(object)
    illegalMove = pyqtSignal(str)
    selectionChanged = pyqtSignal()

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self._selected: int | None = None
        self._hover: int | None = None
        self._flash: int | None = None
        self._suggestion: chess.Move | None = None
        self._suggestion_stale = False
        self._interactive = True
        self.show_coords = True

        self._press_pos: QPointF | None = None
        self._press_was_selected = False
        self._dragging = False
        self._drag_pos: QPointF | None = None

        self.setMinimumSize(240, 240)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)

    def set_suggestion(self, move: chess.Move | None, stale: bool = False) -> None:

        self._suggestion = move
        self._suggestion_stale = stale
        self.update()

    @property
    def suggestion_move(self) -> chess.Move | None:
        return self._suggestion

    def clear_selection(self) -> None:
        if self._selected is not None:
            self._selected = None
            self.selectionChanged.emit()
            self.update()

    def is_interacting(self) -> bool:

        return self._dragging or self._selected is not None

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled
        if not enabled:
            self.clear_selection()

    def board_rect(self) -> QRectF:
        side = min(self.width(), self.height())
        pad = max(11.0, side * 0.036)
        inner = max(40.0, side - 2.0 * pad)
        return QRectF(
            (self.width() - inner) / 2.0,
            (self.height() - inner) / 2.0,
            inner,
            inner,
        )

    def coord_pad(self) -> float:
        return max(11.0, min(self.width(), self.height()) * 0.036)

    def square_size(self) -> float:
        return self.board_rect().width() / 8.0

    def square_rect(self, square: int) -> QRectF:
        rect = self.board_rect()
        size = rect.width() / 8.0
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self.session.flipped:
            col = 7 - file
            row = rank
        else:
            col = file
            row = 7 - rank
        return QRectF(rect.x() + col * size, rect.y() + row * size, size, size)

    def square_at(self, pos: QPointF) -> int | None:
        rect = self.board_rect()
        if not rect.contains(pos):
            return None
        size = rect.width() / 8.0
        col = int((pos.x() - rect.x()) / size)
        row = int((pos.y() - rect.y()) / size)
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        if self.session.flipped:
            file, rank = 7 - col, row
        else:
            file, rank = col, 7 - row
        return chess.square(file, rank)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        rect = self.board_rect()
        if rect.width() <= 1:
            return

        radius = max(4.0, rect.width() * 0.012)
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)

        self._paint_squares(painter, rect)
        self._paint_markers(painter)
        self._paint_pieces(painter)
        self._paint_hints(painter)
        self._paint_drag_piece(painter)
        self._paint_arrow(painter)

        painter.setClipping(False)
        self._paint_coords(painter)
        painter.setPen(QPen(theme.BOARD_EDGE, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

    def _paint_squares(self, painter: QPainter, rect: QRectF) -> None:
        size = rect.width() / 8.0
        painter.setPen(Qt.PenStyle.NoPen)
        for rank in range(8):
            for file in range(8):
                square = chess.square(file, rank)
                color = theme.SQ_DARK if (file + rank) % 2 == 0 else theme.SQ_LIGHT
                painter.fillRect(self.square_rect(square), color)

    def _paint_markers(self, painter: QPainter) -> None:
        board = self.session.board
        last = self.session.last_move
        if last is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.LAST_MOVE)
            for square in (last.from_square, last.to_square):
                painter.drawRect(self.square_rect(square))

        if board.is_check():
            king_sq = board.king(board.turn)
            if king_sq is not None:
                rect = self.square_rect(king_sq)
                grad = QRadialGradient(rect.center(), rect.width() * 0.75)
                grad.setColorAt(0.0, theme.CHECK_GLOW)
                grad.setColorAt(1.0, QColor(248, 90, 90, 0))
                painter.setBrush(grad)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(rect)

        if self._hover is not None and self._hover != self._selected:
            piece = board.piece_at(self._hover)
            if piece is not None and piece.color == board.turn and self._interactive:
                rect = self.square_rect(self._hover)
                painter.setBrush(QColor(255, 255, 255, 26))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)

        if self._selected is not None:
            rect = self.square_rect(self._selected)
            painter.setBrush(theme.SELECTED)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)

        if self._dragging and self._hover is not None and self._selected is not None:
            if self._hover != self._selected and self.session.find_move(
                self._selected, self._hover
            ) is not None:
                rect = self.square_rect(self._hover)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(theme.ACCENT, max(2.0, rect.width() * 0.06)))
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)

        if self._flash is not None:
            rect = self.square_rect(self._flash)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme.WARN, max(2.0, rect.width() * 0.06)))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)

    def _paint_pieces(self, painter: QPainter) -> None:
        board = self.session.board
        for square, piece in board.piece_map().items():
            if self._dragging and square == self._selected:
                continue
            rect = self.square_rect(square)
            is_white = piece.color == chess.WHITE
            fill = theme.PIECE_WHITE_FILL if is_white else theme.PIECE_BLACK_FILL
            edge = theme.PIECE_WHITE_EDGE if is_white else theme.PIECE_BLACK_EDGE
            pieces.draw_piece(painter, rect, piece.piece_type, is_white, fill, edge)

    def _paint_hints(self, painter: QPainter) -> None:
        if self._selected is None or not self._interactive:
            return
        size = self.square_size()
        board = self.session.board
        painter.setPen(Qt.PenStyle.NoPen)
        for move in self.session.legal_from(self._selected):
            rect = self.square_rect(move.to_square)
            target = board.piece_at(move.to_square)
            if target is None:
                radius = size * 0.13
                painter.setBrush(theme.HINT_DOT)
                painter.drawEllipse(rect.center(), radius, radius)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(theme.HINT_RING, max(2.0, size * 0.055)))
                inset = size * 0.07
                painter.drawEllipse(rect.adjusted(inset, inset, -inset, -inset))
                painter.setPen(Qt.PenStyle.NoPen)

    def _paint_drag_piece(self, painter: QPainter) -> None:
        if not self._dragging or self._selected is None or self._drag_pos is None:
            return
        piece = self.session.board.piece_at(self._selected)
        if piece is None:
            return
        size = self.square_size()
        rect = QRectF(
            self._drag_pos.x() - size / 2.0,
            self._drag_pos.y() - size / 2.0,
            size,
            size,
        )
        is_white = piece.color == chess.WHITE
        fill = theme.PIECE_WHITE_FILL if is_white else theme.PIECE_BLACK_FILL
        edge = theme.PIECE_WHITE_EDGE if is_white else theme.PIECE_BLACK_EDGE
        painter.save()
        painter.setOpacity(0.94)
        pieces.draw_piece(painter, rect, piece.piece_type, is_white, fill, edge)
        painter.restore()

    def _paint_coords(self, painter: QPainter) -> None:
        if not getattr(self, "show_coords", True):
            return
        rect = self.board_rect()
        size = rect.width() / 8.0
        pad = self.coord_pad()
        font = QFont(theme.UI_FONT)
        font.setPixelSize(max(7, int(pad * 0.88)))
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(theme.TEXT_FAINT)
        metrics = QFontMetricsF(font)
        ascent, descent = metrics.ascent(), metrics.descent()
        letter_baseline = rect.bottom() + pad * 0.02 + ascent

        for i in range(8):

            file_index = 7 - i if self.session.flipped else i
            letter = FILES[file_index]
            cx = rect.x() + i * size + size / 2
            painter.drawText(
                QPointF(cx - metrics.horizontalAdvance(letter) / 2.0, letter_baseline),
                letter,
            )

            rank_index = i if self.session.flipped else 7 - i
            number = str(rank_index + 1)
            cy = rect.y() + i * size + size / 2 + (ascent - descent) / 2.0
            painter.drawText(
                QPointF(rect.left() - pad * 0.72, cy),
                number,
            )

    def _paint_arrow(self, painter: QPainter) -> None:
        move = self._suggestion
        if move is None:
            return
        size = self.square_size()
        start = self.square_rect(move.from_square).center()
        end = self.square_rect(move.to_square).center()
        base = theme.STALE if self._suggestion_stale else theme.ACCENT

        vec = end - start
        length = math.hypot(vec.x(), vec.y())
        if length < size * 0.2:
            return
        ux, uy = vec.x() / length, vec.y() / length
        nx, ny = -uy, ux

        tail = QPointF(start.x() + ux * size * 0.22, start.y() + uy * size * 0.22)
        head_tip = QPointF(end.x() - ux * size * 0.16, end.y() - uy * size * 0.16)
        shaft_w = max(2.2, size * 0.095)
        head_w = max(shaft_w * 2.3, size * 0.30)
        head_len = max(size * 0.26, min(size * 0.42, length * 0.38))
        neck = QPointF(head_tip.x() - ux * head_len, head_tip.y() - uy * head_len)

        path = QPainterPath()
        path.moveTo(tail.x() + nx * shaft_w / 2, tail.y() + ny * shaft_w / 2)
        path.lineTo(neck.x() + nx * shaft_w / 2, neck.y() + ny * shaft_w / 2)
        path.lineTo(neck.x() + nx * head_w / 2, neck.y() + ny * head_w / 2)
        path.lineTo(head_tip)
        path.lineTo(neck.x() - nx * head_w / 2, neck.y() - ny * head_w / 2)
        path.lineTo(neck.x() - nx * shaft_w / 2, neck.y() - ny * shaft_w / 2)
        path.lineTo(tail.x() - nx * shaft_w / 2, tail.y() - ny * shaft_w / 2)
        path.closeSubpath()

        fill = QColor(base)
        fill.setAlpha(120 if self._suggestion_stale else 215)
        painter.setPen(QPen(QColor(0, 0, 0, 80), 1.2,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(fill)
        painter.drawPath(path)

    def _reject(self, square: int, reason: str) -> None:

        self._flash = square
        self._flash_timer.start(420)
        self.illegalMove.emit(reason)
        self.update()

    def _why_not(self, square: int) -> str:

        board = self.session.board
        piece = board.piece_at(square)
        if piece is None:
            return "这里没有棋子"
        side = "白方" if piece.color == chess.WHITE else "黑方"
        if piece.color != board.turn:
            return f"现在轮到{self.session.turn_name}走，{side}棋子暂时不能动"
        return "这枚棋子现在没有可走的着法"

    def _commit(self, move: chess.Move) -> None:
        self._selected = None
        self.selectionChanged.emit()
        self.update()
        self.movePlayed.emit(move)

    def mousePressEvent(self, event) -> None:
        if not self._interactive or event.button() != Qt.MouseButton.LeftButton:
            return
        square = self.square_at(event.position())
        if square is None:
            self.clear_selection()
            return

        board = self.session.board
        piece = board.piece_at(square)

        if self._selected is not None and square != self._selected:
            move = self.session.find_move(self._selected, square)
            if move is not None:
                self._commit(move)
                return
            if piece is not None and self.session.legal_from(square):
                self._select(square)
                return
            if piece is not None:
                self._reject(square, self._why_not(square))
                return
            self._reject(self._selected, "这一步走不了")
            return

        if piece is None:
            if self._selected is not None:
                self.clear_selection()
            return

        if not self.session.legal_from(square):
            self._reject(square, self._why_not(square))
            return

        self._press_pos = event.position()
        self._press_was_selected = self._selected == square
        self._dragging = False
        self._select(square)

    def _select(self, square: int) -> None:
        if self._selected != square:
            self._selected = square
            self.selectionChanged.emit()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()

        if (
            self._press_pos is not None
            and not self._dragging
            and event.buttons() & Qt.MouseButton.LeftButton
            and (pos - self._press_pos).manhattanLength() > 4
        ):
            self._dragging = True
            self._drag_pos = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            return

        if self._dragging:
            self._drag_pos = pos
            self._hover = self.square_at(pos)
            self.update()
            return

        square = self.square_at(pos)
        if square != self._hover:
            self._hover = square
            self.update()
        piece = self.session.board.piece_at(square) if square is not None else None
        if self._interactive and piece is not None and self.session.legal_from(square):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        was_dragging = self._dragging
        self._dragging = False
        self._drag_pos = None
        self._press_pos = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if was_dragging:
            target = self.square_at(event.position())
            origin = self._selected
            if target is not None and origin is not None and target != origin:
                move = self.session.find_move(origin, target)
                if move is not None:
                    self._commit(move)
                    return

            self.update()
            return

        square = self.square_at(event.position())
        if square is None:
            return
        if square == self._selected and self._press_was_selected:
            self.clear_selection()
        self._press_was_selected = False

    def leaveEvent(self, event) -> None:
        if self._hover is not None:
            self._hover = None
            self.update()

    def _clear_flash(self) -> None:
        self._flash = None
        self.update()
