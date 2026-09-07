import multiprocessing
import runpy
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from vkdub.ui.background_check import BackgroundCheck
from vkdub.ui.main_window import MainWindow
from vkdub.ui.theme import DARK_THEME
from vkdub.utils.logging import configure_logging
from vkdub.utils.paths import resource_path
from vkdub.version import APP_NAME, __version__


def run_cli_or_worker() -> int | None:
    """If invoked as a CLI or subprocess worker (e.g. from frozen executable),
    execute the requested command/module without launching the PySide6 GUI.
    Returns integer exit code if handled, or None if GUI should run.
    """
    if len(sys.argv) <= 1:
        return None

    args = list(sys.argv[1:])

    # Strip standard Python flags (-u, -s, -B, -O)
    while args and args[0] in ("-u", "-s", "-B", "-O"):
        args.pop(0)

    if not args:
        return None

    # Case 1: python -m <module_name> [args...]
    if args[0] == "-m" and len(args) > 1:
        module_name = args[1]
        sys.argv = [module_name] + args[2:]
        try:
            runpy.run_module(module_name, run_name="__main__", alter_sys=True)
            return 0
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        except Exception:
            import traceback

            traceback.print_exc()
            return 1

    # Case 2: python <script_path.py> [args...]
    if args[0].endswith(".py") or Path(args[0]).is_file():
        script_path = args[0]
        sys.argv = [script_path] + args[1:]
        try:
            runpy.run_path(script_path, run_name="__main__")
            return 0
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        except Exception:
            import traceback

            traceback.print_exc()
            return 1

    return None


def create_application() -> QApplication:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("vanhkhuc")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME)

    icon_path = resource_path("icon.ico")
    if not icon_path.is_file():
        icon_path = resource_path("icon.png")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    app.aboutToQuit.connect(BackgroundCheck.shutdown)
    return app


def main() -> int:
    multiprocessing.freeze_support()
    cli_code = run_cli_or_worker()
    if cli_code is not None:
        return cli_code

    app = create_application()
    window = MainWindow()
    window.show()
    return app.exec()

