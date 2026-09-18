"""Entry point for KAPPAK Studio application."""

import sys
from PySide6.QtWidgets import QApplication
from kappak.ui.shell import KappakShell


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    shell = KappakShell()
    shell.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
