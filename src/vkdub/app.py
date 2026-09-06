import sys

from PySide6.QtWidgets import QApplication

from vkdub.ui.background_check import BackgroundCheck
from vkdub.ui.main_window import MainWindow
from vkdub.ui.theme import DARK_THEME
from vkdub.utils.logging import configure_logging
from vkdub.version import APP_NAME, __version__


def create_application() -> QApplication:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("vanhkhuc")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME)
    app.aboutToQuit.connect(BackgroundCheck.shutdown)
    return app


def main() -> int:
    app = create_application()
    window = MainWindow()
    window.show()
    return app.exec()
