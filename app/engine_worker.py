from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

import chess
import chess.engine
from PyQt6.QtCore import QThread, pyqtSignal

@dataclass
class AnalysisResult:
    version: int
    uci: str = ""
    san: str = ""
    cp: int | None = None
    mate: int | None = None
    depth: int = 0
    pv: list[str] = field(default_factory=list)
    nodes: int = 0
    elapsed_ms: int = 0
    interrupted: bool = False

class EngineWorker(QThread):
    ready = pyqtSignal(str)
    failed = pyqtSignal(str)
    progress = pyqtSignal(object)
    analysisDone = pyqtSignal(object)

    def __init__(
        self,
        engine_path: str,
        threads: int = 2,
        hash_mb: int = 64,
        low_priority: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.engine_path = engine_path
        self.threads = threads
        self.hash_mb = hash_mb
        self.low_priority = low_priority

        self._engine: chess.engine.SimpleEngine | None = None
        self._cond = threading.Condition()
        self._pending: tuple[int, chess.Board, int] | None = None
        self._cancel = threading.Event()
        self._quit = False
        self._dead = False
        self._last_progress = 0.0

    def submit(self, version: int, board: chess.Board, movetime_ms: int) -> None:

        with self._cond:
            self._pending = (version, board.copy(stack=True), int(movetime_ms))
            self._cancel.set()
            self._cond.notify()

    def cancel(self) -> None:

        self._cancel.set()

    def shutdown(self) -> None:
        with self._cond:
            self._quit = True
            self._cancel.set()
            self._cond.notify_all()

    def run(self) -> None:
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            options: dict[str, object] = {}
            if "Threads" in self._engine.options:
                options["Threads"] = self.threads
            if "Hash" in self._engine.options:
                options["Hash"] = self.hash_mb
            if options:
                self._engine.configure(options)
            self._lower_priority()
            name = str(self._engine.id.get("name") or "Stockfish")
            self.ready.emit(name)
        except Exception as exc:
            self._dead = True
            self.failed.emit(f"引擎启动失败：{exc}")
            return

        while True:
            with self._cond:
                while self._pending is None and not self._quit:
                    self._cond.wait(0.5)
                if self._quit:
                    break
                job = self._pending
                self._pending = None
                self._cancel.clear()

            if job is None:
                continue
            self._analyse(*job)

        try:
            if self._engine is not None:
                self._engine.quit()
        except Exception:
            pass
        finally:
            self._engine = None

    def _lower_priority(self) -> None:

        if not self.low_priority or os.name != "nt" or self._engine is None:
            return
        try:
            import ctypes

            transport = getattr(self._engine.protocol, "transport", None)
            pid = transport.get_pid() if transport is not None else None
            if not pid:
                return
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0200 | 0x0400, False, pid)
            if handle:
                kernel32.SetPriorityClass(handle, 0x00004000)
                kernel32.CloseHandle(handle)
        except Exception:
            pass

    def _analyse(self, version: int, board: chess.Board, movetime_ms: int) -> None:
        if self._engine is None:
            return

        started = time.monotonic()
        best_info: dict | None = None
        interrupted = False
        self._last_progress = 0.0

        try:
            limit = chess.engine.Limit(time=max(0.05, movetime_ms / 1000.0))
            with self._engine.analysis(board, limit) as analysis:
                for info in analysis:
                    if self._cancel.is_set():
                        interrupted = True
                        break
                    if info.get("pv"):
                        best_info = info
                        self._emit_progress(version, info)
        except chess.engine.EngineTerminatedError as exc:
            self._dead = True
            self.failed.emit(f"引擎异常退出：{exc}")
            return
        except Exception as exc:
            self.failed.emit(f"分析失败：{exc}")
            return

        result = AnalysisResult(version=version, interrupted=interrupted)
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        if best_info:
            pv = list(best_info.get("pv") or [])
            if pv:
                result.pv = [m.uci() for m in pv]
                move = pv[0]
                result.uci = move.uci()
                try:
                    result.san = board.san(move)
                except Exception:
                    result.san = result.uci
            score = best_info.get("score")
            if score is not None:
                try:
                    white_score = score.pov(chess.WHITE)
                    if white_score.is_mate():
                        result.mate = white_score.mate()
                    else:
                        result.cp = white_score.score()
                except Exception:
                    pass
            result.depth = int(best_info.get("depth") or 0)
            result.nodes = int(best_info.get("nodes") or 0)

        self.analysisDone.emit(result)

    def _emit_progress(self, version: int, info: dict) -> None:
        now = time.monotonic()
        if now - self._last_progress < 0.12:
            return
        self._last_progress = now
        cp = None
        mate = None
        score = info.get("score")
        if score is not None:
            try:
                white_score = score.pov(chess.WHITE)
                if white_score.is_mate():
                    mate = white_score.mate()
                else:
                    cp = white_score.score()
            except Exception:
                return
        self.progress.emit(
            {
                "version": version,
                "depth": int(info.get("depth") or 0),
                "cp": cp,
                "mate": mate,
            }
        )
