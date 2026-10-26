from __future__ import annotations

from PyQt6.QtGui import QColor

CARD_BG = QColor(17, 19, 24, 236)
CARD_BORDER = QColor(255, 255, 255, 30)
HEADER_BG = QColor(255, 255, 255, 9)
FOOTER_BG = QColor(0, 0, 0, 40)

TEXT = QColor(230, 234, 242)
TEXT_DIM = QColor(146, 154, 170)
TEXT_FAINT = QColor(104, 112, 128)

ACCENT = QColor(74, 222, 128)
ACCENT_SOFT = QColor(74, 222, 128, 60)
STALE = QColor(158, 168, 186)
WARN = QColor(248, 113, 113)
GOOD = QColor(74, 222, 128)

SQ_LIGHT = QColor(223, 226, 233)
SQ_DARK = QColor(97, 109, 128)
BOARD_EDGE = QColor(0, 0, 0, 90)

LAST_MOVE = QColor(255, 205, 100, 70)
SELECTED = QColor(255, 205, 100, 115)
HINT_DOT = QColor(52, 168, 118, 135)
HINT_RING = QColor(52, 168, 118, 165)
CHECK_GLOW = QColor(248, 90, 90, 150)

PIECE_WHITE_FILL = QColor(250, 251, 253)
PIECE_WHITE_EDGE = QColor(24, 26, 32)
PIECE_BLACK_FILL = QColor(26, 28, 34)
PIECE_BLACK_EDGE = QColor(228, 232, 240)

UI_FONT = "Segoe UI"

QSS = """
QWidget {
    color: #e6eaf2;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
}

QToolButton {
    color: #b9c2d4;
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 3px 7px;
    font-size: 13px;
}
QToolButton:hover { background: rgba(255,255,255,0.10); color: #ffffff; }
QToolButton:pressed { background: rgba(255,255,255,0.18); }
QToolButton:checked { background: rgba(74,222,128,0.18); color: #74de8c; }
QToolButton:disabled { color: #5c6474; }

QLabel#Title { color: #eef2f8; font-size: 12px; font-weight: 600; }
QLabel#Status { color: #96a0b4; font-size: 11px; }
QLabel#Eval   { color: #cfd6e4; font-size: 12px; font-weight: 600;
                font-family: "Consolas", "Cascadia Mono", monospace; }
QLabel#Warn   { color: #f87171; font-size: 11px; }
QLabel#Pct    { color: #7f8a9e; font-size: 10px;
                font-family: "Consolas", "Cascadia Mono", monospace; }

QPushButton {
    color: #e6eaf2;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 7px;
    padding: 7px 14px;
}
QPushButton:hover { background: rgba(255,255,255,0.14); }
QPushButton:pressed { background: rgba(255,255,255,0.20); }
QPushButton#Primary {
    background: rgba(74,222,128,0.20);
    border: 1px solid rgba(74,222,128,0.45);
    color: #d8ffe4;
    font-weight: 600;
}
QPushButton#Primary:hover { background: rgba(74,222,128,0.30); }

QSlider::groove:horizontal {
    height: 5px;
    background: rgba(255,255,255,0.14);
    border-radius: 2.5px;
}
QSlider::sub-page:horizontal {
    background: rgba(74,222,128,0.55);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #dfe6f2;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover { background: #ffffff; }

QSpinBox, QLineEdit {
    color: #e6eaf2;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: rgba(74,222,128,0.35);
}
QCheckBox { color: #cfd6e4; }
QDialog { background: #14161c; }
"""
