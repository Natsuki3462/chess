from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import chess
import chess.engine
from PyQt6.QtCore import QCoreApplication, QTimer

import config
from engine_worker import EngineWorker
from session import Session

PASS = "[PASS]"
FAIL = "[FAIL]"
_failures: list[str] = []

def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{PASS if ok else FAIL} {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        _failures.append(name)

def test_session() -> None:
    s = Session()
    check("初始 FEN", s.fen.startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"))
    check("初始 version=0", s.version == 0)

    ok = s.push(chess.Move.from_uci("e2e4"))
    check("e2e4 合法", ok and s.ply == 1 and s.version == 1)
    check("非法着法被拒", not s.push(chess.Move.from_uci("e2e5")))
    s.push(chess.Move.from_uci("e7e5"))
    s.push(chess.Move.from_uci("g1f3"))
    check("三步后 SAN", s.san_list() == ["e4", "e5", "Nf3"], str(s.san_list()))

    s.undo()
    check("撤销一步", s.ply == 2 and s.fen.split()[0].startswith("rnbqkbnr"))
    check("可重做", s.can_redo)
    s.redo()
    check("重做", s.ply == 3)

    s.jump_to(1)
    check("回退到第 1 步", s.ply == 1 and s.san_list() == ["e4"], str(s.san_list()))
    s.jump_to(3)
    check("前进到第 3 步", s.ply == 3 and s.san_list() == ["e4", "e5", "Nf3"])

    s.reset(chess.BLACK)
    check("新局复位", s.ply == 0 and s.my_color == chess.BLACK and s.version > 0)

    b = Session()
    b.board = chess.Board("8/P7/8/8/8/8/8/K6k w - - 0 1")
    move = b.find_move(chess.A7, chess.A8)
    check("升变默认升后", move is not None and move.promotion == chess.QUEEN)

    f1 = b.fen
    b.toggle_flip()
    check("翻转不改 FEN", b.fen == f1)

def test_engine_sync(path: str) -> None:
    started = time.monotonic()
    engine = chess.engine.SimpleEngine.popen_uci(path)
    engine.configure({"Threads": 2, "Hash": 64})
    boot = time.monotonic() - started
    board = chess.Board()
    info = engine.analyse(board, chess.engine.Limit(time=0.5))
    best = info["pv"][0]
    check("引擎冷启动 < 3s", boot < 3.0, f"{boot*1000:.0f} ms")
    check("起始局面给出合法着法", best in board.legal_moves, best.uci())
    engine.quit()

def test_worker(path: str) -> None:

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    worker = EngineWorker(path, 2, 64)
    results: list = []
    state = {"ready": False}

    def on_ready(name: str) -> None:
        state["ready"] = True
        print(f"      引擎就绪：{name}")

    worker.ready.connect(on_ready)
    worker.failed.connect(lambda m: print(f"      {FAIL} {m}"))
    worker.analysisDone.connect(lambda r: results.append(r))
    worker.start()

    board = chess.Board()
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]
    deadline = time.monotonic() + 10
    while not state["ready"] and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    check("worker 引擎就绪", state["ready"])
    if not state["ready"]:
        return

    worker.submit(1, board, 500)
    deadline = time.monotonic() + 8
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    ok = bool(results) and results[0].version == 1 and results[0].uci in {
        m.uci() for m in board.legal_moves
    }
    check("worker 单次分析", ok, results[0].uci if results else "无结果")

    results.clear()
    for i, uci in enumerate(moves, start=2):
        board.push(chess.Move.from_uci(uci))
        worker.submit(i, board, 600)
        time.sleep(0.05)

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
        if any(r.version == len(moves) + 1 for r in results):
            break

    final = [r for r in results if r.version == len(moves) + 1]
    ok = bool(final) and final[-1].uci in {m.uci() for m in board.legal_moves}
    check("快速打断后最终结果正确", ok, final[-1].uci if final else "无结果")
    stale = [r for r in results if r.version != len(moves) + 1]
    print(f"      被丢弃的过期结果：{len(stale)} 个（符合预期，主线程按 version 过滤）")

    board.pop()
    worker.submit(99, board, 400)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
        if any(r.version == 99 for r in results):
            break
    final99 = [r for r in results if r.version == 99]
    ok = bool(final99) and final99[-1].uci in {m.uci() for m in board.legal_moves}
    check("撤销后立即分析", ok, final99[-1].uci if final99 else "无结果")

    worker.shutdown()
    worker.wait(4000)

def main() -> int:
    print("== ChessFloat 自检 ==")
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    path = config.find_engine()
    check("找到 Stockfish", path is not None, str(path))
    if path is None:
        return 1

    print("\n-- 棋局状态机 --")
    test_session()

    print("\n-- 引擎直连 --")
    test_engine_sync(str(path))

    print("\n-- 引擎线程 --")
    test_worker(str(path))

    print("\n== 结果 ==")
    if _failures:
        print(f"{FAIL} {len(_failures)} 项未通过：{', '.join(_failures)}")
        return 1
    print(f"{PASS} 全部通过")
    return 0

if __name__ == "__main__":
    sys.exit(main())
