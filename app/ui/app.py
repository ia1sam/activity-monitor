from __future__ import annotations

import argparse
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.bootstrap import build_app_context
from app.ui.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Activity Monitor UI")
    parser.add_argument(
        "--storage",
        choices=["sqlite", "csv", "both"],
        default="sqlite",
        help="Storage backend for activity records",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow(build_app_context(storage=args.storage))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
