from __future__ import annotations

import sys
import traceback
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

import config
from float_window import FloatWindow

def _install_excepthook() -> None:
    def hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            sys.stderr.write(text)
            sys.stderr.flush()
        except Exception:
            pass
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("ChessFloat 出错了")
        box.setText("程序遇到未处理的错误，界面可能已失效。")
        box.setDetailedText(text[-4000:])
        box.exec()

    sys.excepthook = hook

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ChessFloat")
    app.setApplicationDisplayName("ChessFloat")
    app.setOrganizationName("ChessFloat")
    app.setQuitOnLastWindowClosed(True)

    _install_excepthook()

    cfg = config.load_config()
    window = FloatWindow(cfg)
    window.show()
    window.raise_()
    window.activateWindow()

    for index, arg in enumerate(sys.argv):
        if arg == "--selftest-ms" and index + 1 < len(sys.argv):
            try:
                delay = int(sys.argv[index + 1])
            except ValueError:
                delay = 2000
            QTimer.singleShot(delay, app.quit)
            break

    code = app.exec()
    config.save_config(window.cfg)
    return code

if __name__ == "__main__":
    sys.exit(main())
