from __future__ import annotations

import chess
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

_CACHE: dict[int, tuple[QPainterPath, QRectF]] = {}

def _rounded(x: float, y: float, w: float, h: float, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), r, r)
    return path

def _pawn() -> QPainterPath:
    head = QPainterPath()
    head.addEllipse(QPointF(50, 30), 12.5, 12.5)

    body = QPainterPath()
    body.moveTo(50, 41)
    body.cubicTo(58, 44, 61, 56, 62, 68)
    body.lineTo(67, 72)
    body.lineTo(69, 80)
    body.lineTo(31, 80)
    body.lineTo(33, 72)
    body.lineTo(38, 68)
    body.cubicTo(39, 56, 42, 44, 50, 41)
    body.closeSubpath()

    base = _rounded(24, 79, 52, 13, 4)
    return head.united(body).united(base)

def _rook() -> QPainterPath:
    crown = QPainterPath()
    crown.moveTo(25, 10)
    crown.lineTo(37, 10)
    crown.lineTo(37, 19)
    crown.lineTo(44, 19)
    crown.lineTo(44, 10)
    crown.lineTo(56, 10)
    crown.lineTo(56, 19)
    crown.lineTo(63, 19)
    crown.lineTo(63, 10)
    crown.lineTo(75, 10)
    crown.lineTo(75, 30)
    crown.lineTo(25, 30)
    crown.closeSubpath()

    body = QPainterPath()
    body.moveTo(31, 28)
    body.lineTo(69, 28)
    body.lineTo(64, 74)
    body.lineTo(36, 74)
    body.closeSubpath()

    base = _rounded(24, 73, 52, 14, 4)
    return crown.united(body).united(base)

def _knight() -> QPainterPath:
    body = QPainterPath()
    body.moveTo(72, 92)
    body.lineTo(72, 74)
    body.cubicTo(70, 58, 65, 44, 58, 33)
    body.cubicTo(56, 27, 55, 21, 54, 17)
    body.lineTo(49, 6)
    body.cubicTo(45, 12, 41, 16, 37, 21)
    body.cubicTo(31, 28, 23, 35, 19, 43)
    body.cubicTo(15, 47, 14, 53, 19, 55)
    body.cubicTo(25, 58, 31, 59, 35, 65)
    body.cubicTo(35, 74, 33, 82, 30, 92)
    body.closeSubpath()

    base = _rounded(24, 84, 54, 10, 3)
    return body.united(base)

def _bishop() -> QPainterPath:
    ball = QPainterPath()
    ball.addEllipse(QPointF(50, 13), 5.5, 5.5)

    mitre = QPainterPath()
    mitre.moveTo(50, 19)
    mitre.cubicTo(39, 28, 33, 40, 33, 50)
    mitre.lineTo(67, 50)
    mitre.cubicTo(67, 40, 61, 28, 50, 19)
    mitre.closeSubpath()

    collar = _rounded(30, 49, 40, 9, 3)

    body = QPainterPath()
    body.moveTo(38, 57)
    body.lineTo(62, 57)
    body.lineTo(65, 74)
    body.lineTo(35, 74)
    body.closeSubpath()

    base = _rounded(24, 73, 52, 14, 4)
    return ball.united(mitre).united(collar).united(body).united(base)

def _queen() -> QPainterPath:
    crown = QPainterPath()
    crown.moveTo(19, 41)
    crown.lineTo(22, 16)
    crown.lineTo(31, 33)
    crown.lineTo(36, 12)
    crown.lineTo(44, 32)
    crown.lineTo(50, 9)
    crown.lineTo(56, 32)
    crown.lineTo(64, 12)
    crown.lineTo(69, 33)
    crown.lineTo(78, 16)
    crown.lineTo(81, 41)
    crown.closeSubpath()

    pearls = QPainterPath()
    for cx, cy in ((22, 16), (36, 12), (50, 9), (64, 12), (78, 16)):
        pearls.addEllipse(QPointF(cx, cy), 4.2, 4.2)

    collar = _rounded(28, 40, 44, 9, 3)

    body = QPainterPath()
    body.moveTo(37, 48)
    body.lineTo(63, 48)
    body.lineTo(66, 74)
    body.lineTo(34, 74)
    body.closeSubpath()

    base = _rounded(23, 73, 54, 14, 4)
    path = crown.united(pearls).united(collar).united(body).united(base)
    return path.simplified()

def _king() -> QPainterPath:
    cross = QPainterPath()
    cross.moveTo(46, 4)
    cross.lineTo(54, 4)
    cross.lineTo(54, 14)
    cross.lineTo(64, 14)
    cross.lineTo(64, 22)
    cross.lineTo(54, 22)
    cross.lineTo(54, 33)
    cross.lineTo(46, 33)
    cross.lineTo(46, 22)
    cross.lineTo(36, 22)
    cross.lineTo(36, 14)
    cross.lineTo(46, 14)
    cross.closeSubpath()

    crown = QPainterPath()
    crown.moveTo(33, 30)
    crown.cubicTo(40, 36, 60, 36, 67, 30)
    crown.lineTo(68, 40)
    crown.lineTo(32, 40)
    crown.closeSubpath()

    collar = _rounded(30, 39, 40, 9, 3)

    body = QPainterPath()
    body.moveTo(38, 47)
    body.lineTo(62, 47)
    body.lineTo(66, 74)
    body.lineTo(34, 74)
    body.closeSubpath()

    base = _rounded(23, 73, 54, 14, 4)
    path = cross.united(crown).united(collar).united(body).united(base)
    return path.simplified()

_BUILDERS = {
    chess.PAWN: _pawn,
    chess.KNIGHT: _knight,
    chess.BISHOP: _bishop,
    chess.ROOK: _rook,
    chess.QUEEN: _queen,
    chess.KING: _king,
}

def piece_path(piece_type: int) -> tuple[QPainterPath, QRectF]:
    cached = _CACHE.get(piece_type)
    if cached is not None:
        return cached
    builder = _BUILDERS.get(piece_type)
    if builder is None:
        raise KeyError(piece_type)
    path = builder()
    path.setFillRule(Qt.FillRule.WindingFill)
    entry = (path, path.boundingRect())
    _CACHE[piece_type] = entry
    return entry

def _detail(piece_type: int) -> list[QPainterPath]:

    lines: list[QPainterPath] = []
    if piece_type == chess.ROOK:
        for y in (36, 64):
            p = QPainterPath()
            p.moveTo(33, y)
            p.lineTo(67, y)
            lines.append(p)
    elif piece_type == chess.BISHOP:
        p = QPainterPath()
        p.moveTo(50, 24)
        p.lineTo(57, 40)
        lines.append(p)
    elif piece_type == chess.KNIGHT:
        eye = QPainterPath()
        eye.addEllipse(QPointF(38, 30), 2.6, 2.6)
        lines.append(eye)
        nostril = QPainterPath()
        nostril.addEllipse(QPointF(21, 49), 2.0, 2.0)
        lines.append(nostril)
    elif piece_type == chess.PAWN:
        p = QPainterPath()
        p.moveTo(42, 45)
        p.lineTo(58, 45)
        lines.append(p)
    return lines

def draw_piece(
    painter: QPainter,
    rect: QRectF,
    piece_type: int,
    is_white: bool,
    fill: QColor,
    edge: QColor,
    stroke_ratio: float = 0.028,
) -> None:
    path, bounds = piece_path(piece_type)
    if bounds.width() <= 0 or bounds.height() <= 0:
        return

    pad = rect.width() * 0.075
    avail = rect.adjusted(pad, pad, -pad, -pad)
    scale = min(avail.width() / bounds.width(), avail.height() / bounds.height())
    if scale <= 0:
        return

    painter.save()
    painter.translate(
        avail.center().x() - bounds.center().x() * scale,
        avail.center().y() - bounds.center().y() * scale,
    )
    painter.scale(scale, scale)

    stroke = max(0.9, rect.width() * stroke_ratio) / scale

    painter.save()
    painter.translate(0.0, 1.6)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 55 if is_white else 70))
    painter.drawPath(path)
    painter.restore()

    pen = QPen(
        edge,
        stroke,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(pen)
    painter.setBrush(fill)
    painter.drawPath(path)

    detail_pen = QPen(
        edge,
        stroke * 0.85,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(detail_pen)
    painter.setBrush(edge)
    for line in _detail(piece_type):
        painter.drawPath(line)

    painter.restore()
