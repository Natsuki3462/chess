from __future__ import annotations

import chess
from PyQt6.QtCore import QObject, pyqtSignal

class Session(QObject):
    positionChanged = pyqtSignal(int)
    historyChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.board = chess.Board()
        self.my_color: chess.Color = chess.WHITE
        self.flipped: bool = False
        self.version: int = 0
        self._redo: list[chess.Move] = []
        self._san_cache: tuple[int, list[str]] | None = None

    @property
    def ply(self) -> int:
        return len(self.board.move_stack)

    @property
    def last_move(self) -> chess.Move | None:
        return self.board.peek() if self.board.move_stack else None

    @property
    def is_my_turn(self) -> bool:
        return self.board.turn == self.my_color

    @property
    def turn_name(self) -> str:
        return "白方" if self.board.turn == chess.WHITE else "黑方"

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def fen(self) -> str:
        return self.board.fen()

    def san_list(self) -> list[str]:

        if self._san_cache and self._san_cache[0] == self.version:
            return self._san_cache[1]
        replay = chess.Board()
        out: list[str] = []
        for move in self.board.move_stack:
            try:
                out.append(replay.san(move))
            except Exception:
                out.append(replay.uci(move))
            replay.push(move)
        self._san_cache = (self.version, out)
        return out

    def legal_from(self, square: int) -> list[chess.Move]:
        return [m for m in self.board.legal_moves if m.from_square == square]

    def find_move(self, from_sq: int, to_sq: int) -> chess.Move | None:

        candidates = [
            m for m in self.board.legal_moves
            if m.from_square == from_sq and m.to_square == to_sq
        ]
        if not candidates:
            return None
        for m in candidates:
            if m.promotion == chess.QUEEN:
                return m
        return candidates[0]

    def reset(self, my_color: chess.Color | None = None) -> None:
        if my_color is not None:
            self.my_color = my_color
        self.board = chess.Board()
        self._redo.clear()
        self.bump()

    def push(self, move: chess.Move) -> bool:
        if move not in self.board.legal_moves:
            return False
        self.board.push(move)
        self._redo.clear()
        self.bump()
        return True

    def push_uci(self, uci: str) -> bool:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False
        return self.push(move)

    def undo(self) -> bool:
        if not self.board.move_stack:
            return False
        self._redo.append(self.board.pop())
        self.bump()
        return True

    def undo_many(self, n: int) -> int:
        done = 0
        for _ in range(max(0, n)):
            if not self.undo_silent():
                break
            done += 1
        if done:
            self.bump()
        return done

    def undo_silent(self) -> bool:
        if not self.board.move_stack:
            return False
        self._redo.append(self.board.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        move = self._redo.pop()
        if move not in self.board.legal_moves:
            self._redo.clear()
            return False
        self.board.push(move)
        self.bump()
        return True

    def jump_to(self, ply: int) -> bool:

        target = max(0, min(ply, self.ply + len(self._redo)))
        changed = False
        while self.ply > target:
            if not self.undo_silent():
                break
            changed = True
        while self.ply < target:
            if not self._redo:
                break
            move = self._redo[-1]
            if move not in self.board.legal_moves:
                self._redo.clear()
                break
            self._redo.pop()
            self.board.push(move)
            changed = True
        if changed:
            self.bump()
        return changed

    def toggle_flip(self) -> None:
        self.flipped = not self.flipped

        self.historyChanged.emit()

    def bump(self) -> None:
        self.version += 1
        self.positionChanged.emit(self.version)
        self.historyChanged.emit()

    def eval_text(self, cp: int | None, mate: int | None) -> str:

        if mate is not None:
            return f"#{mate}" if mate > 0 else f"#-{abs(mate)}"
        if cp is None:
            return "—"
        value = cp / 100.0
        return f"{value:+.2f}"
