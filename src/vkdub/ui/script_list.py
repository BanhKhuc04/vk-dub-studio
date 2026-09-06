from PySide6.QtCore import Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget


class ScriptList(QListWidget):
    move_requested = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dropEvent(self, event: QDropEvent) -> None:
        source = self.currentRow()
        target = self.indexAt(event.position().toPoint()).row()
        if target < 0:
            target = self.count() - 1
        event.ignore()  # The domain validates before any visual/model order changes.
        if source >= 0 and target >= 0 and source != target:
            self.move_requested.emit(source, target)
