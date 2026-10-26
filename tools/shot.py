from __future__ import annotations

import os
import sys
import time
from pathlib import Path

if os.environ.get("CHESSFLOAT_OFFSCREEN") == "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
OUT = Path(__file__).resolve().parent / "shots"
OUT.mkdir(exist_ok=True)

import chess
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import (
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import config
from float_window import FloatWindow

SIZE = (470, 578)

def pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)

def wait_for(app: QApplication, predicate, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
        if predicate():
            return True
    return False

def compose(window: FloatWindow, path: Path) -> None:

    pix = window.grab()
    canvas = QPixmap(pix.size())
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, canvas.width(), canvas.height())
    grad.setColorAt(0.0, QColor(38, 52, 78))
    grad.setColorAt(0.5, QColor(72, 92, 120))
    grad.setColorAt(1.0, QColor(146, 120, 96))
    painter.fillRect(canvas.rect(), grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 26))
    painter.drawEllipse(QPoint(90, 120), 120, 120)
    painter.setBrush(QColor(255, 210, 120, 40))
    painter.drawEllipse(QPoint(canvas.width() - 70, canvas.height() - 120), 150, 150)

    painter.setOpacity(max(0.05, window.windowOpacity()))
    painter.drawPixmap(0, 0, pix)
    painter.end()
    canvas.save(str(path))
    print(f"  已保存 {path.name}  {pix.width()}x{pix.height()}")

def square_center(window: FloatWindow, square: int) -> QPoint:
    rect = window.board.square_rect(square)
    point = rect.center().toPoint()
    return point

def click_square(window: FloatWindow, square: int) -> None:
    QTest.mouseClick(
        window.board,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        square_center(window, square),
    )

def _send_move(widget, pos: QPointF) -> None:

    event = QMouseEvent(
        QEvent.Type.MouseMove,
        pos,
        QPointF(widget.mapToGlobal(pos.toPoint())),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)

def drag_begin(window: FloatWindow, square: int) -> QPoint:
    point = square_center(window, square)
    QTest.mousePress(
        window.board, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )
    return point

def drag_to(window: FloatWindow, from_point: QPoint, square: int) -> None:
    target = square_center(window, square)
    mid = QPointF((from_point.x() + target.x()) / 2.0, (from_point.y() + target.y()) / 2.0)
    _send_move(window.board, mid)
    _send_move(window.board, QPointF(target))

def drag_end(window: FloatWindow, square: int) -> None:
    QTest.mouseRelease(
        window.board,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        square_center(window, square),
    )

def drag(window: FloatWindow, src: int, dst: int) -> None:
    point = drag_begin(window, src)
    drag_to(window, point, dst)
    drag_end(window, dst)

def send_wheel(widget, delta_y: int, ctrl: bool = False) -> None:

    mods = (
        Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    )
    pos = QPointF(widget.width() / 2.0, widget.height() / 2.0)
    glob = QPointF(widget.mapToGlobal(pos.toPoint()))
    event = QWheelEvent(
        pos,
        glob,
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        mods,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)

def main() -> int:
    app = QApplication(sys.argv)
    cfg = config.load_config()
    cfg["geometry"] = [40, 40, *SIZE]
    cfg["opacity"] = 0.94
    cfg["analysis_ms"] = 700
    cfg["debounce_ms"] = 200

    window = FloatWindow(cfg)
    window.resize(*SIZE)
    window.show()
    pump(app, 0.6)

    compose(window, OUT / "01_choose_side.png")

    window.choose_side(True)
    pump(app, 0.3)
    click_square(window, chess.E2)
    pump(app, 0.15)
    compose(window, OUT / "02_selection_hints.png")
    click_square(window, chess.E2)
    pump(app, 0.1)

    got = wait_for(app, lambda: window._suggestion is not None, 8.0)
    print(f"  [{'PASS' if got else 'FAIL'}] 开局建议："
          f"{window._suggestion.san if got else '超时'} "
          f"(深度 {window._suggestion.depth if got else '-'})")
    compose(window, OUT / "03_suggestion_arrow.png")

    click_square(window, chess.E2)
    pump(app, 0.12)
    click_square(window, chess.E4)
    pump(app, 0.25)
    ok_click = window.session.san_list() == ["e4"]
    print(f"  [{'PASS' if ok_click else 'FAIL'}] 点击 e2→e4 复刻着法：{window.session.san_list()}")

    compose(window, OUT / "10_stale_arrow.png")
    kept = window.board.suggestion_move
    stale = window.board._suggestion_stale
    print(f"  [{'PASS' if kept is not None and stale else 'FAIL'}] 走子后箭头仍保留（灰）"
          f" → {kept.uci() if kept else '无'}")
    pump(app, 1.8)
    print(f"  [{'PASS' if window._suggestion is None else 'FAIL'}] 对手回合不产出对方建议 "
          f"(suggestion={window._suggestion.san if window._suggestion else None})")

    window._play_move(chess.Move.from_uci("e7e5"))
    got = wait_for(app, lambda: window._suggestion is not None, 8.0)
    arrow = window.board.suggestion_move
    ok = got and arrow is not None and not window.board._suggestion_stale
    print(f"  [{'PASS' if ok else 'FAIL'}] 轮到我方出绿箭头 → "
          f"{arrow.uci() if arrow else '无'}")
    window._play_move(chess.Move.from_uci("g1f3"))
    pump(app, 0.2)
    window._play_move(chess.Move.from_uci("b8c6"))
    got = wait_for(app, lambda: window._suggestion is not None, 8.0)
    compose(window, OUT / "04_midgame.png")

    before = window.session.ply
    window.accept_suggestion()
    pump(app, 0.3)
    print(f"  [{'PASS' if window.session.ply == before + 1 else 'FAIL'}] 空格采纳建议 → "
          f"{window.session.san_list()}")

    window.flip()
    pump(app, 0.3)
    compose(window, OUT / "05_flipped.png")
    window.flip()

    window.toggle_compact()
    pump(app, 0.3)
    compose(window, OUT / "06_compact.png")
    window.toggle_compact()
    pump(app, 0.2)

    ply = window.session.ply
    window.undo()
    pump(app, 0.25)
    print(f"  [{'PASS' if window.session.ply == ply - 1 else 'FAIL'}] 撤销一步")
    arrow = window.board.suggestion_move
    restored = arrow is not None and not window.board._suggestion_stale
    print(f"  [{'PASS' if restored else 'FAIL'}] 撤销后箭头立即恢复原色（不用等重新分析）→ "
          f"{arrow.uci() if arrow else '无'}")
    ply_now = window.session.ply
    window.accept_suggestion()
    pump(app, 0.25)
    ok = window.session.ply == ply_now + 1
    print(f"  [{'PASS' if ok else 'FAIL'}] 恢复出来的箭头可直接空格走 → "
          f"{window.session.san_list()[-1] if ok else '无'}")
    window.jump_to(2)
    pump(app, 0.2)
    print(f"  [{'PASS' if window.session.ply == 2 else 'FAIL'}] 回退到第 2 步 → "
          f"{window.session.san_list()}")

    geo_before = window.geometry()
    op_before = window.windowOpacity()
    window._set_always_on_top(False)
    pump(app, 0.2)
    window._set_always_on_top(True)
    pump(app, 0.2)
    ok = (window.geometry() == geo_before) and abs(window.windowOpacity() - op_before) < 0.01
    print(f"  [{'PASS' if ok else 'FAIL'}] 置顶开关保持几何与透明度")

    footer = window.footer
    footer.slider.setValue(15)
    pump(app, 0.15)
    ok_min = abs(window.windowOpacity() - 0.15) < 0.02
    footer.slider.setValue(100)
    pump(app, 0.15)
    ok_max = abs(window.windowOpacity() - 1.0) < 0.02
    print(f"  [{'PASS' if ok_min and ok_max else 'FAIL'}] 透明度范围 15%–100% "
          f"(15%→{0.15:.2f}, 100%→{1.0:.2f})")

    footer.slider.setValue(94)
    pump(app, 0.1)
    send_wheel(window.board, -120, ctrl=True)
    pump(app, 0.12)
    ok_wheel = abs(window.windowOpacity() - 0.92) < 0.015
    print(f"  [{'PASS' if ok_wheel else 'FAIL'}] 棋盘上 Ctrl+滚轮 无级调节 → "
          f"{window.windowOpacity():.2f}（一格 -2%）")

    before = window.windowOpacity()
    send_wheel(window.board, -120, ctrl=False)
    pump(app, 0.12)
    ok_plain = abs(window.windowOpacity() - before) < 0.005
    print(f"  [{'PASS' if ok_plain else 'FAIL'}] 普通滚轮不改变透明度")

    before = window.windowOpacity()
    QTest.keyClick(window, Qt.Key.Key_Up)
    pump(app, 0.12)
    ok_key = abs(window.windowOpacity() - (before + 0.02)) < 0.015
    print(f"  [{'PASS' if ok_key else 'FAIL'}] ↑ 键单次微调 2% → {window.windowOpacity():.2f}")

    footer.btn_icon.click()
    pump(app, 0.15)
    ok_reset = abs(window.windowOpacity() - 0.94) < 0.015
    print(f"  [{'PASS' if ok_reset else 'FAIL'}] ◐ 一键复位 → {window.windowOpacity():.2f}")

    footer.slider.setValue(52)
    pump(app, 0.2)
    compose(window, OUT / "08_opacity.png")
    footer.slider.setValue(94)
    pump(app, 0.1)

    window.new_game()
    pump(app, 0.2)
    print(f"  [{'PASS' if not window._side_chosen else 'FAIL'}] 新局回到选择先后手")
    window.choose_side(False)
    pump(app, 0.4)
    ok = window.session.flipped and window.session.my_color == chess.BLACK
    print(f"  [{'PASS' if ok else 'FAIL'}] 执黑：视角翻转、白方在顶部")

    pump(app, 1.6)
    no_arrow = window.board.suggestion_move is None and window._suggestion is None
    print(f"  [{'PASS' if no_arrow else 'FAIL'}] 执黑开局不显示对方建议（无箭头、不分析）")

    click_square(window, chess.E1)
    pump(app, 0.15)
    no_move_hint = "没有可走的着法" in window.header.status.text()
    print(f"  [{'PASS' if no_move_hint else 'FAIL'}] 点无着法可走的白王给出提示："
          f"{window.header.status.text()}")

    click_square(window, chess.E7)
    pump(app, 0.15)
    hinted = "轮到白方" in window.header.status.text()
    print(f"  [{'PASS' if hinted else 'FAIL'}] 点不该走的黑棋给出提示："
          f"{window.header.status.text()}")
    print(f"  [{'PASS' if window.board._selected is None else 'FAIL'}] 未把不可动的棋子设为选中")

    click_square(window, chess.E2)
    pump(app, 0.15)
    selected = window.board._selected == chess.E2
    compose(window, OUT / "09_black_hints.png")
    click_square(window, chess.E4)
    pump(app, 0.3)
    ok = selected and window.session.san_list() == ["e4"]
    print(f"  [{'PASS' if ok else 'FAIL'}] 执黑点白棋复刻 e2→e4 → {window.session.san_list()}")

    got = wait_for(app, lambda: window._suggestion is not None, 8.0)
    arrow = window.board.suggestion_move
    ok = got and arrow is not None and not window.board._suggestion_stale
    print(f"  [{'PASS' if ok else 'FAIL'}] 轮到我方出绿箭头 → "
          f"{arrow.uci() if arrow else '无'} "
          f"(深度 {window._suggestion.depth if got else '-'})")
    compose(window, OUT / "07_black_view.png")

    window.new_game()
    pump(app, 0.2)
    window.choose_side(True)
    wait_for(app, lambda: window._suggestion is not None, 8.0)

    point = drag_begin(window, chess.D2)
    drag_to(window, point, chess.D4)
    pump(app, 0.2)
    dragging_ok = window.board._dragging
    compose(window, OUT / "11_dragging.png")
    drag_end(window, chess.D4)
    pump(app, 0.3)
    ok = dragging_ok and window.session.san_list() == ["d4"]
    print(f"  [{'PASS' if ok else 'FAIL'}] 拖拽 d2→d4 走子 → {window.session.san_list()}")

    kept = window.board.suggestion_move
    print(f"  [{'PASS' if kept is not None and window.board._suggestion_stale else 'FAIL'}] "
          f"拖拽走子后箭头仍保留（灰）→ {kept.uci() if kept else '无'}")

    drag(window, chess.D7, chess.E5)
    pump(app, 0.25)
    ok = window.session.san_list() == ["d4"] and window.board._selected == chess.D7
    print(f"  [{'PASS' if ok else 'FAIL'}] 拖到非法位置回弹（保持选中）→ "
          f"选中 {chess.square_name(window.board._selected) if window.board._selected is not None else '无'}")

    drag(window, chess.D7, chess.D5)
    pump(app, 0.3)
    ok = window.session.san_list() == ["d4", "d5"]
    print(f"  [{'PASS' if ok else 'FAIL'}] 拖拽复刻对手 d7→d5 → {window.session.san_list()}")

    window.flip()
    pump(app, 0.3)
    drag(window, chess.E2, chess.E4)
    pump(app, 0.3)
    ok = window.session.san_list() == ["d4", "d5", "e4"]
    print(f"  [{'PASS' if ok else 'FAIL'}] 翻转视角下拖拽 e2→e4 → {window.session.san_list()}")
    window.flip()

    window.new_game()
    pump(app, 0.2)
    window.choose_side(True)
    got = wait_for(app, lambda: window._suggestion is not None, 8.0)
    pump(app, 0.9)
    ok = got and window.session.ply == 0 and not window.cfg["auto_accept"]
    print(f"  [{'PASS' if ok else 'FAIL'}] 开关关闭时只出箭头、不走子 "
          f"(ply={window.session.ply})")

    window.header.btn_auto.setChecked(True)
    pump(app, 0.8)
    ok = window.cfg["auto_accept"] and window.session.ply == 1
    print(f"  [{'PASS' if ok else 'FAIL'}] 打开开关后立即采纳当前建议 → "
          f"{window.session.san_list()}")

    window._play_move(chess.Move.from_uci("e7e5"))
    pump(app, 0.2)
    ply_before = window.session.ply
    auto = wait_for(app, lambda: window.session.ply > ply_before, 8.0)
    print(f"  [{'PASS' if auto else 'FAIL'}] 自动采纳在循环中生效 → "
          f"{window.session.san_list()}")
    compose(window, OUT / "12_auto_accept.png")

    ply_before = window.session.ply
    window.undo()
    pump(app, 0.9)
    ok = (not window.cfg["auto_accept"]) and window.session.ply == ply_before - 1
    print(f"  [{'PASS' if ok else 'FAIL'}] 撤销后自动暂停（不会被立刻走回去）→ "
          f"ply={window.session.ply}, auto={window.cfg['auto_accept']}, "
          f"按钮={window.header.btn_auto.isChecked()}")
    print(f"  [{'PASS' if not window.header.btn_auto.isChecked() else 'FAIL'}] "
          f"顶栏开关同步取消勾选")

    window.header.btn_auto.setChecked(False)
    pump(app, 0.2)
    ply_before = window.session.ply
    got = wait_for(app, lambda: window._suggestion is not None, 8.0)
    pump(app, 0.9)
    ok = got and window.session.ply == ply_before
    print(f"  [{'PASS' if ok else 'FAIL'}] 关闭后只出箭头、不再自动走子 "
          f"(ply={window.session.ply}, 建议={window._suggestion.san if window._suggestion else None})")

    window.set_strength("economy")
    pump(app, 0.6)
    ok = (window.cfg["analysis_ms"], window.cfg["threads"], window.cfg["hash_mb"]) == (800, 2, 64)
    print(f"  [{'PASS' if ok else 'FAIL'}] 切到省电档 → "
          f"{window.cfg['analysis_ms']}ms/{window.cfg['threads']}T/{window.cfg['hash_mb']}MB")

    window.set_strength("balanced")
    pump(app, 0.8)
    ok = (window.cfg["analysis_ms"], window.cfg["threads"], window.cfg["hash_mb"]) == (2000, 4, 256)
    print(f"  [{'PASS' if ok else 'FAIL'}] 切到均衡档 → "
          f"{window.cfg['analysis_ms']}ms/{window.cfg['threads']}T/{window.cfg['hash_mb']}MB")
    print(f"  [{'PASS' if window._engine_ok else 'FAIL'}] 换档后引擎重新就绪")

    base = int(window.cfg["analysis_ms"])
    opening = chess.Board()
    midgame = chess.Board("r2q1rk1/pp2bppp/2n1bn2/2pp4/3P4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 0 10")
    endgame = chess.Board("8/5pk1/6p1/8/8/6P1/5PK1/3R4 w - - 0 40")
    endgame_check = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4K2r w - - 0 1")
    t_open = window._movetime_for(opening)
    t_mid = window._movetime_for(midgame)
    t_end = window._movetime_for(endgame)
    t_end2 = window._movetime_for(endgame_check)
    print(f"      限时分配（基础 {base}ms）：开局 {t_open} / 中局 {t_mid} / "
          f"残局 {t_end} / 残局+将军 {t_end2}")
    ok = t_end >= base * 1.5 and t_open <= base * 1.05
    print(f"  [{'PASS' if ok else 'FAIL'}] 残局自动加时、普通局面不额外加时")

    window.cfg["adaptive"] = False
    ok = window._movetime_for(endgame) == base
    print(f"  [{'PASS' if ok else 'FAIL'}] 关闭自适应 → 固定 {base}ms")
    window.cfg["adaptive"] = True

    saved_engine = window.cfg.get("engine_path")
    saved_finder = config.find_engine
    window._stop_engine()
    window.cfg["engine_path"] = ""
    config.find_engine = lambda explicit=None: None
    window._start_engine()
    pump(app, 0.4)
    hint = window.header.status.text()
    ok = window._engine_error is not None and "未找到" in hint
    print(f"  [{'PASS' if ok else 'FAIL'}] 引擎缺失时状态栏说明原因：{hint}")

    window.choose_side(True)
    pump(app, 0.4)
    still = "未找到" in window.header.status.text()
    print(f"  [{'PASS' if still else 'FAIL'}] 选完先后手后提示仍在（不被覆盖）："
          f"{window.header.status.text()}")

    window._play_move(chess.Move.from_uci("e2e4"))
    pump(app, 0.3)
    ok = window.session.ply == 1 and "未找到" in window.header.status.text()
    print(f"  [{'PASS' if ok else 'FAIL'}] 无引擎仍可手动走子且提示不消失")

    config.find_engine = saved_finder
    window.cfg["engine_path"] = saved_engine or ""
    window._start_engine()
    pump(app, 1.2)
    ok = window._engine_ok and window._engine_error is None
    print(f"  [{'PASS' if ok else 'FAIL'}] 恢复引擎后重新就绪（错误提示清除）")

    window.close()
    pump(app, 0.5)
    return 0

if __name__ == "__main__":
    sys.exit(main())
