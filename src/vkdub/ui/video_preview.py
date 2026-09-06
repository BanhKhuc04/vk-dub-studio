from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
)

from vkdub.media.ffprobe import VideoMetadata
from vkdub.ui.left_config_panel import label
from vkdub.ui.video_canvas import VideoCanvas


def clock_text(milliseconds: int) -> str:
    seconds = max(0, milliseconds) // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"



class VideoPreview(QFrame):
    playback_error = Signal(str)
    mask_requested = Signal()
    subtitle_requested = Signal()
    subtitle_box_toggled = Signal(bool)
    preview_voice_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        self.title = label("Xem trước video", "heading")
        header.addWidget(self.title)
        header.addStretch()
        layout.addLayout(header)

        # Main Video Canvas (Maximized)
        self.video = VideoCanvas()
        layout.addWidget(self.video, 1)

        self.empty_hint = label("Tải video MP4 để bắt đầu. Video gốc được giữ nguyên.")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setStyleSheet("color: #929fb5; font-size: 13px; margin: 8px;")
        layout.addWidget(self.empty_hint)

        # Audio Output & Media Player
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.70)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoSink(self.video.sink)

        # Timeline seek bar
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.setEnabled(False)
        self.seek.setAccessibleName("Vị trí phát video")
        layout.addWidget(self.seek)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.play_button = QPushButton("▶ Phát")
        self.play_button.setEnabled(False)
        self.play_button.setStyleSheet("font-weight: bold; min-width: 80px;")
        controls.addWidget(self.play_button)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-family: Consolas; font-weight: 600; color: #e5eaf4;")
        controls.addWidget(self.time_label)

        # Volume control
        vol_label = QLabel("🔊")
        controls.addWidget(vol_label)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setMaximumWidth(80)
        self.volume.setAccessibleName("Âm lượng xem trước")
        controls.addWidget(self.volume)

        controls.addStretch()

        # Key action buttons (as specified in Section 11)
        self.btn_mask = QPushButton("▣ Khung dịch / Xóa chữ")
        self.btn_mask.setToolTip(
            "Khung chọn khu vực phụ đề cần che/dịch · Kéo để di chuyển · Kéo góc để đổi kích thước"
        )
        self.btn_mask.clicked.connect(self._mask_clicked)

        self.btn_subtitle = QPushButton("✥ Vị trí & kiểu Sub")
        self.btn_subtitle.setToolTip("Mở chỉnh phụ đề; kéo khung trên video để đổi vị trí")
        self.btn_subtitle.clicked.connect(self._subtitle_clicked)

        self.btn_sub_box = QPushButton("▣ Khung Sub")
        self.btn_sub_box.setCheckable(True)
        self.btn_sub_box.setToolTip("Bật/tắt hộp nền phía sau phụ đề")
        self.btn_sub_box.toggled.connect(self.subtitle_box_toggled.emit)

        self.btn_preview_voice = QPushButton("Preview Voice")
        self.btn_preview_voice.setToolTip("Nghe thử voice lồng tiếng (Giai đoạn 5)")
        self.btn_preview_voice.clicked.connect(self._voice_preview_clicked)

        # More actions menu (...)
        self.btn_more = QToolButton()
        self.btn_more.setText("⋯")
        self.btn_more.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px 8px;")
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self)
        act_info = QAction("ℹ Thông tin chi tiết video", self)
        act_info.triggered.connect(self._show_info_dialog)
        act_snap = QAction("📸 Chụp ảnh khung hình hiện tại", self)
        act_snap.triggered.connect(self._capture_frame)
        more_menu.addAction(act_info)
        more_menu.addAction(act_snap)
        self.btn_more.setMenu(more_menu)

        actions = QHBoxLayout()
        for btn in (
            self.btn_mask,
            self.btn_subtitle,
            self.btn_sub_box,
            self.btn_preview_voice,
            self.btn_more,
        ):
            btn.setStyleSheet("padding: 6px 10px; font-weight: 600;")
            actions.addWidget(btn)

        layout.addLayout(controls)
        layout.addLayout(actions)

        # Concise Metadata label
        self.metadata_label = label("Chưa có metadata.")
        self.metadata_label.setStyleSheet("color: #72d7c1; font-size: 11px;")
        layout.addWidget(self.metadata_label)

        self._last_metadata: VideoMetadata | None = None

        # Connect events
        self.play_button.clicked.connect(self.toggle_playback)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.positionChanged.connect(self._position_changed)
        self.player.playbackStateChanged.connect(self._state_changed)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.seekableChanged.connect(self.seek.setEnabled)
        self.player.errorOccurred.connect(self._error)
        self.seek.sliderReleased.connect(lambda: self.player.setPosition(self.seek.value()))
        self.seek.valueChanged.connect(self._seek_changed)
        self.volume.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))

    def _mask_clicked(self) -> None:
        self.mask_requested.emit()

    def _subtitle_clicked(self) -> None:
        self.subtitle_requested.emit()

    def set_subtitle_box_checked(self, checked: bool) -> None:
        self.btn_sub_box.blockSignals(True)
        self.btn_sub_box.setChecked(checked)
        self.btn_sub_box.blockSignals(False)

    def _voice_preview_clicked(self) -> None:
        self.preview_voice_requested.emit()

    def _show_info_dialog(self) -> None:
        if not self._last_metadata:
            QMessageBox.information(
                self, "Thông tin video", "Chưa có thông tin metadata của video."
            )
            return
        m = self._last_metadata
        fps = f"{m.fps:.3f} fps" if m.fps else "N/A"
        msg = (
            f"Kích thước: {m.width} × {m.height}\n"
            f"Thời lượng: {clock_text(round(m.duration * 1000))} ({m.duration:.2f}s)\n"
            f"Tốc độ khung hình: {fps}\n"
            f"Dung lượng: {m.size_bytes / 1024 / 1024:.2f} MB\n"
            f"Video Codec: {m.video_codec}\n"
            f"Audio Codec: {m.audio_codec or 'Không có'}"
        )
        QMessageBox.information(self, "Thông tin chi tiết video", msg)

    def _capture_frame(self) -> None:
        if not self.video.frame_image.isNull():
            path, _ = QFileDialog.getSaveFileName(
                self, "Lưu khung hình", "frame.png", "Hình ảnh (*.png *.jpg)"
            )
            if path:
                self.video.frame_image.save(path)
                QMessageBox.information(self, "Chụp ảnh", f"Đã lưu ảnh vào:\n{path}")
                return
        QMessageBox.information(
            self, "Chụp ảnh", "Không có khung hình video để chụp hoặc video chưa phát."
        )

    def load(self, path: Path | None) -> None:
        self.player.stop()
        self.player.setSource(QUrl())
        self.video.clear()
        self.title.setText(path.name if path else "Xem trước video")
        self.title.setToolTip(str(path) if path else "")
        self.empty_hint.setVisible(path is None)
        self.play_button.setEnabled(False)
        self.seek.setEnabled(False)
        self.seek.setRange(0, 0)
        self.metadata_label.setText("Đang đọc metadata…" if path else "Chưa có metadata.")
        self._position_changed(0)
        if path:
            self.player.setSource(QUrl.fromLocalFile(str(path)))

    def show_metadata(self, metadata: VideoMetadata) -> None:
        self._last_metadata = metadata
        fps = f"{metadata.fps:.2f} fps" if metadata.fps else ""
        audio = metadata.audio_codec or "không có audio"
        dur_str = clock_text(round(metadata.duration * 1000))
        size_mb = f"{metadata.size_bytes / 1024 / 1024:.1f} MB"
        self.metadata_label.setText(
            f"✓ {metadata.width} × {metadata.height}  •  {dur_str}  •  "
            f"{size_mb}  •  {metadata.video_codec}/{audio}  {fps}"
        )

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
            self.player.play()

    def _duration_changed(self, duration: int) -> None:
        self.seek.setMaximum(duration)
        self._position_changed(self.player.position())

    def _position_changed(self, position: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.blockSignals(True)
            self.seek.setValue(position)
            self.seek.blockSignals(False)
        self.time_label.setText(f"{clock_text(position)} / {clock_text(self.player.duration())}")

    def _seek_changed(self, value: int) -> None:
        if not self.seek.isSliderDown():
            self.player.setPosition(value)
        self.time_label.setText(f"{clock_text(value)} / {clock_text(self.player.duration())}")

    def _state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self.play_button.setText(
            "⏸ Tạm dừng" if state == QMediaPlayer.PlaybackState.PlayingState else "▶ Phát"
        )

    def _media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        usable = status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.EndOfMedia,
        )
        self.play_button.setEnabled(usable)
        self.seek.setEnabled(usable and self.player.isSeekable())

    def _error(self, error: QMediaPlayer.Error, message: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            self.play_button.setEnabled(False)
            self.seek.setEnabled(False)
            self.empty_hint.setText("Không phát được video. Kiểm tra tệp và codec.")
            self.empty_hint.show()
            self.playback_error.emit(f"Không phát được video: {message}")
