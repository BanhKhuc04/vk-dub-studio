import pytest
from PySide6.QtWidgets import QWidget
from vkdub.ui.toast import ToastManager, ToastNotification, ToastType


def test_toast_creation_and_dismiss(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(800, 600)
    parent.show()

    manager = ToastManager(parent)
    toast = manager.show_toast(
        title="Thành công",
        message="Đã xuất dự án CapCut",
        toast_type=ToastType.SUCCESS,
        duration_ms=10000,
    )

    assert toast is not None
    assert len(manager.active_toasts) == 1
    assert toast.isVisible()

    # Dismiss
    toast.dismiss()
    toast._on_fade_out_finished()
    assert len(manager.active_toasts) == 0


def test_toast_types(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    manager = ToastManager(parent)

    t_info = manager.show_toast("Info", "Test Info", ToastType.INFO)
    t_warn = manager.show_toast("Warning", "Test Warning", ToastType.WARNING)
    t_err = manager.show_toast("Error", "Test Error", ToastType.ERROR)

    assert len(manager.active_toasts) == 3
    assert t_info.isVisible()
    assert t_warn.isVisible()
    assert t_err.isVisible()
