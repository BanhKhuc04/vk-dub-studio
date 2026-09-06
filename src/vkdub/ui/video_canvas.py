from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtMultimedia import QVideoFrame, QVideoSink
from PySide6.QtWidgets import QToolButton, QWidget

from vkdub.domain.mask import MaskItem
from vkdub.domain.subtitle import SUBTITLE_REFERENCE_HEIGHT, SubtitleStyle
from vkdub.ui.blur_image import feathered_blur, reconstructed_background


class VideoCanvas(QWidget):
    """Paint decoded frames in the widget, avoiding a separate native video surface.

    This keeps Windows preview, paused frames and screenshots consistent. Qt still
    performs demux/decode/audio scheduling; only the current display frame is retained.
    Also renders real-time subtitle overlay and mask items.
    """

    mask_rect_changed = Signal(str, float, float, float, float)  # id, x, y, w, h
    mask_selected = Signal(str)  # mask_id
    mask_delete_requested = Signal(str)
    subtitle_margin_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.frame_image = QImage()
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self._frame_changed)
        self.setMinimumSize(320, 220)
        self.current_subtitle: str = ""
        self.subtitle_style: SubtitleStyle | None = None
        self.masks: list[MaskItem] = []
        self.current_time_ms: int = 0
        self.active_mask_id: str | None = None
        self.interactive_mask_mode: bool = False
        self.subtitle_edit_mode: bool = False
        self._target_rect = QRect()
        self._subtitle_rect = QRect()
        self._subtitle_drag_start: QPoint | None = None
        self._subtitle_drag_margin: int | None = None
        self._drag_start_pos: QPoint | None = None
        self._drag_mode: str | None = None
        self._drag_rect: tuple[float, float, float, float] | None = None
        self._blur_cache: dict[str, tuple[tuple[object, ...], QImage]] = {}
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.delete_mask_button = QToolButton(self)
        self.delete_mask_button.setText("×")
        self.delete_mask_button.setToolTip("Xóa vùng xóa chữ (Delete)")
        self.delete_mask_button.setAccessibleName("Xóa vùng xóa chữ")
        self.delete_mask_button.setFixedSize(26, 26)
        self.delete_mask_button.setStyleSheet(
            "QToolButton { background: #193637; color: white; border: 1px solid #61ddcd;"
            " border-radius: 5px; font-size: 20px; padding: 0; }"
            "QToolButton:hover { background: #b03545; }"
        )
        self.delete_mask_button.clicked.connect(self._delete_selected)
        self.delete_mask_button.hide()

    def _frame_changed(self, frame: QVideoFrame) -> None:
        if frame.isValid():
            self.frame_image = frame.toImage()
            self.update()

    def set_subtitle(self, text: str, style: SubtitleStyle | None = None) -> None:
        if text != self.current_subtitle or style != self.subtitle_style:
            self.current_subtitle = text
            self.subtitle_style = style
            self.update()

    def set_masks(
        self,
        masks: list[MaskItem],
        active_id: str | None = None,
        time_ms: int | None = None,
    ) -> None:
        self.masks = list(masks)
        self._blur_cache.clear()
        self.active_mask_id = active_id
        if time_ms is not None:
            self.current_time_ms = time_ms
        self.update()

    def set_current_time(self, time_ms: int) -> None:
        if time_ms != self.current_time_ms:
            self.current_time_ms = time_ms
            self.update()

    def clear(self) -> None:
        self.frame_image = QImage()
        self.current_subtitle = ""
        self.masks = []
        self.active_mask_id = None
        self._drag_mode = None
        self._drag_start_pos = None
        self._target_rect = QRect()
        self._subtitle_rect = QRect()
        self._subtitle_drag_start = None
        self._subtitle_drag_margin = None
        self._blur_cache.clear()
        self.delete_mask_button.hide()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#05070b"))
        target_rect = self.rect()
        if not self.frame_image.isNull():
            size = self.frame_image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(0, 0, size.width(), size.height())
            target.moveCenter(self.rect().center())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, self.frame_image)
            target_rect = target
        self._target_rect = target_rect

        # 1. Paint Masks
        if self.masks:
            self._paint_masks(painter, target_rect)
        self._position_delete_button()

        # 2. Paint Subtitles
        self._subtitle_rect = QRect()
        if self.current_subtitle and self.subtitle_style:
            self._paint_subtitle(painter, target_rect, self.current_subtitle, self.subtitle_style)

        painter.end()

    def _mask_rect(self, mask: MaskItem) -> QRect:
        x, y, w, h = mask.to_pixel_rect(self._target_rect.width(), self._target_rect.height())
        return QRect(x, y, w, h).translated(self._target_rect.topLeft())

    def _selected_mask(self) -> MaskItem | None:
        return next(
            (
                m
                for m in self.masks
                if m.id == self.active_mask_id and m.is_active_at(self.current_time_ms)
            ),
            None,
        )

    def _position_delete_button(self) -> None:
        mask = self._selected_mask()
        visible = bool(mask and self.interactive_mask_mode and not self.frame_image.isNull())
        if visible and mask:
            rect = self._mask_rect(mask)
            # Above the top-right corner, leaving its resize handle free.
            x = min(self.width() - 28, rect.right() - 12)
            y = rect.top() - 34
            if y < 0:
                x = min(self.width() - 28, rect.right() + 10)
                y = max(0, rect.top() + 10)
            self.delete_mask_button.move(max(0, x), y)
        self.delete_mask_button.setVisible(visible)

    def _paint_masks(self, painter: QPainter, frame_rect: QRect) -> None:
        if self.frame_image.isNull() or frame_rect.isEmpty():
            return
        display_frame = self.frame_image.scaled(
            frame_rect.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        prefix: tuple[object, ...] = (
            self.frame_image.cacheKey(),
            frame_rect.width(),
            frame_rect.height(),
        )
        for mask in self.masks:
            if not mask.is_active_at(self.current_time_ms):
                continue
            rect = self._mask_rect(mask)
            local = rect.translated(-frame_rect.topLeft())
            prefix += (local.x(), local.y(), local.width(), local.height())
            if mask.mask_type == "solid":
                # Keep existing solid masks in saved projects compatible.
                color = QColor(mask.color)
                color.setAlphaF(max(0.1, min(1.0, mask.opacity)))
                painter.fillRect(rect, color)
                composite = QPainter(display_frame)
                composite.fillRect(local, color)
                composite.end()
                prefix += (color.rgba(),)
            else:
                prefix += (mask.mask_type, mask.blur_strength)
                key = prefix
                cached = self._blur_cache.get(mask.id)
                if cached is None or cached[0] != key:
                    effect = (
                        reconstructed_background(display_frame, local, mask.blur_strength)
                        if mask.mask_type == "erase"
                        else feathered_blur(display_frame, local, mask.blur_strength)
                    )
                    self._blur_cache[mask.id] = (key, effect)
                painter.drawImage(rect, self._blur_cache[mask.id][1])
                # Later masks sample this result, so overlap never restores sharp pixels.
                composite = QPainter(display_frame)
                composite.drawImage(local, self._blur_cache[mask.id][1])
                composite.end()

            if self.interactive_mask_mode and mask.id == self.active_mask_id:
                painter.setPen(QPen(QColor("#61ddcd"), 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
                painter.setBrush(QColor("#61ddcd"))
                for corner in (
                    rect.topLeft(),
                    rect.topRight(),
                    rect.bottomLeft(),
                    rect.bottomRight(),
                ):
                    painter.drawRect(QRect(corner.x() - 3, corner.y() - 3, 6, 6))

    def _hit_mode(self, rect: QRect, pos: QPoint) -> str | None:
        corners = {
            "nw": rect.topLeft(),
            "ne": rect.topRight(),
            "sw": rect.bottomLeft(),
            "se": rect.bottomRight(),
        }
        for name, point in corners.items():
            if (pos - point).manhattanLength() <= 12:
                return name
        return "move" if rect.contains(pos) else None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self.subtitle_edit_mode
            and event.button() == Qt.MouseButton.LeftButton
            and self._subtitle_rect.contains(event.position().toPoint())
            and self.subtitle_style is not None
        ):
            self._subtitle_drag_start = event.position().toPoint()
            self._subtitle_drag_margin = self.subtitle_style.margin_bottom
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.setFocus()
            return
        if (
            not self.interactive_mask_mode
            or self.frame_image.isNull()
            or event.button() != Qt.MouseButton.LeftButton
        ):
            super().mousePressEvent(event)
            return
        pos = event.position().toPoint()
        selected = self._selected_mask()
        candidates = ([selected] if selected else []) + [
            m for m in reversed(self.masks) if m is not selected
        ]
        for mask in candidates:
            if not mask.is_active_at(self.current_time_ms):
                continue
            mode = self._hit_mode(self._mask_rect(mask), pos)
            if mode:
                self.active_mask_id = mask.id
                self.mask_selected.emit(mask.id)
                self._drag_mode = mode
                self._drag_start_pos = pos
                self._drag_rect = (mask.x, mask.y, mask.width, mask.height)
                self.setFocus()
                self.update()
                return
        self.active_mask_id = None
        self._drag_mode = None
        self._drag_start_pos = None
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self.subtitle_edit_mode
            and self._subtitle_drag_start is not None
            and self._subtitle_drag_margin is not None
            and not self._target_rect.isEmpty()
        ):
            subtitle_dy = event.position().toPoint().y() - self._subtitle_drag_start.y()
            reference_dy = round(
                subtitle_dy * SUBTITLE_REFERENCE_HEIGHT / self._target_rect.height()
            )
            margin = max(10, min(300, self._subtitle_drag_margin - reference_dy))
            self.subtitle_margin_changed.emit(margin)
            return
        if self.subtitle_edit_mode and self._subtitle_rect.contains(event.position().toPoint()):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            return
        if not self.interactive_mask_mode or self._target_rect.isEmpty():
            super().mouseMoveEvent(event)
            return
        pos = event.position().toPoint()
        mask = self._selected_mask()
        if self._drag_start_pos is None or self._drag_rect is None or mask is None:
            mode = None
            for item in reversed(self.masks):
                if item.is_active_at(self.current_time_ms):
                    mode = self._hit_mode(self._mask_rect(item), pos)
                    if mode:
                        break
            cursors = {
                "move": Qt.CursorShape.SizeAllCursor,
                "nw": Qt.CursorShape.SizeFDiagCursor,
                "se": Qt.CursorShape.SizeFDiagCursor,
                "ne": Qt.CursorShape.SizeBDiagCursor,
                "sw": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(cursors.get(mode or "", Qt.CursorShape.ArrowCursor))
            return
        fw, fh = self._target_rect.width(), self._target_rect.height()
        dx = (pos.x() - self._drag_start_pos.x()) / fw
        mask_dy = (pos.y() - self._drag_start_pos.y()) / fh
        x, y, w, h = self._drag_rect
        if self._drag_mode == "move":
            mask.x = max(0.0, min(1.0 - w, x + dx))
            mask.y = max(0.0, min(1.0 - h, y + mask_dy))
        else:
            right, bottom = x + w, y + h
            min_w, min_h = min(w, 20 / fw), min(h, 20 / fh)
            if "w" in (self._drag_mode or ""):
                x = max(0.0, min(right - min_w, x + dx))
            if "e" in (self._drag_mode or ""):
                right = min(1.0, max(x + min_w, right + dx))
            if "n" in (self._drag_mode or ""):
                y = max(0.0, min(bottom - min_h, y + mask_dy))
            if "s" in (self._drag_mode or ""):
                bottom = min(1.0, max(y + min_h, bottom + mask_dy))
            mask.x, mask.y, mask.width, mask.height = x, y, right - x, bottom - y
        self.mask_rect_changed.emit(mask.id, mask.x, mask.y, mask.width, mask.height)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._subtitle_drag_start = None
        self._subtitle_drag_margin = None
        self._drag_mode = None
        self._drag_start_pos = None
        self._drag_rect = None
        super().mouseReleaseEvent(event)

    def _delete_selected(self) -> None:
        if self.interactive_mask_mode and self._selected_mask():
            mask_id = self.active_mask_id
            self._drag_mode = None
            self._drag_start_pos = None
            self.mask_delete_requested.emit(mask_id)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._delete_selected()
        elif event.key() == Qt.Key.Key_Escape:
            self.active_mask_id = None
            self.update()
        else:
            super().keyPressEvent(event)

    def _paint_subtitle(
        self,
        painter: QPainter,
        frame_rect: QRect,
        text: str,
        style: SubtitleStyle,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Scale font relative to target height vs standard 1080p height
        scale = max(0.2, frame_rect.height() / 1080.0)
        scaled_font_size = max(10, int(style.font_size * scale))

        font = QFont(style.font_family, scaled_font_size)
        font.setBold(style.bold)
        font.setItalic(style.italic)
        painter.setFont(font)

        fm = QFontMetrics(font)
        max_w = max(100, int(frame_rect.width() * style.max_width_ratio))

        # Split text into lines wrapped within max_w
        lines: list[str] = []
        for raw_line in text.split("\n"):
            words = raw_line.split()
            if not words:
                continue
            cur_line = words[0]
            for w in words[1:]:
                test_line = f"{cur_line} {w}"
                if fm.horizontalAdvance(test_line) <= max_w:
                    cur_line = test_line
                else:
                    lines.append(cur_line)
                    cur_line = w
            lines.append(cur_line)

        if not lines:
            return

        line_height = int(fm.height() * style.line_spacing)
        total_text_height = line_height * len(lines)
        scaled_margin_bottom = int(style.margin_bottom * scale)

        # Base Y position for bottom-center alignment
        bottom_y = frame_rect.bottom() - scaled_margin_bottom
        top_y = bottom_y - total_text_height

        # Calculate bounding box for background if enabled
        max_line_width = max(fm.horizontalAdvance(line_item) for line_item in lines)
        pad_x = max(6, int(14 * scale))
        pad_y = max(4, int(8 * scale))
        box_rect = QRect(
            frame_rect.center().x() - max_line_width // 2 - pad_x,
            top_y - pad_y,
            max_line_width + pad_x * 2,
            total_text_height + pad_y * 2,
        )
        self._subtitle_rect = box_rect

        if style.background_box:
            bg_color = QColor(style.background_color)
            bg_color.setAlphaF(max(0.0, min(1.0, style.background_opacity)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(box_rect, int(6 * scale), int(6 * scale))

        # Paint each line
        text_color = QColor(style.text_color)
        outline_color = QColor(style.outline_color)
        shadow_color = QColor(style.shadow_color)
        outline_w = max(1.0, style.outline_width * scale)
        shadow_off = max(1.0, style.shadow_offset * scale)

        for i, line in enumerate(lines):
            line_w = fm.horizontalAdvance(line)
            x = frame_rect.center().x() - line_w // 2
            y = top_y + i * line_height + fm.ascent()

            # Create painter path for outline and shadow
            path = QPainterPath()
            path.addText(QPoint(x, y), font, line)

            # Draw shadow
            if style.shadow_offset > 0:
                shadow_path = QPainterPath()
                shadow_path.addText(QPoint(int(x + shadow_off), int(y + shadow_off)), font, line)
                painter.fillPath(shadow_path, shadow_color)

            # Draw outline
            if style.outline_width > 0:
                pen = QPen(
                    outline_color,
                    outline_w * 2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                painter.strokePath(path, pen)

            # Fill text
            painter.fillPath(path, text_color)

        if self.subtitle_edit_mode:
            painter.setPen(QPen(QColor("#61ddcd"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box_rect.adjusted(-3, -3, 3, 3), 4, 4)
