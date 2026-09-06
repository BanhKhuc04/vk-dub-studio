import subprocess

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QDialog, QMessageBox

from vkdub.domain.mask import MaskItem
from vkdub.media.process import find_tool
from vkdub.services.mask_service import build_ffmpeg_mask_filter
from vkdub.services.project_service import load_project
from vkdub.ui.blur_image import feathered_blur, reconstructed_background
from vkdub.ui.main_window import MainWindow
from vkdub.ui.video_canvas import VideoCanvas


def image_pixels(image):
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return (
        np.frombuffer(image.constBits(), np.uint8)
        .reshape(image.height(), image.width(), 4)
        .copy()[:, :, :3]
    )


def striped_image(width=640, height=360):
    pixels = np.zeros((height, width, 4), np.uint8)
    pixels[:, :, :3] = np.where(np.arange(width)[None, :, None] % 4 < 2, 225, 75)
    pixels[:, :, 3] = 255
    return QImage(pixels.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()


def text_over_gradient(width=160, height=100):
    xs = np.arange(width, dtype=np.float32)[None, :]
    ys = np.arange(height, dtype=np.float32)[:, None]
    background = np.empty((height, width, 3), np.uint8)
    background[:, :, 0] = 40 + xs * 0.5 + ys * 0.2
    background[:, :, 1] = 80 + xs * 0.3
    background[:, :, 2] = 120 + ys * 0.5
    pixels = background.copy()
    pixels[42:58, 45:115] = 245
    pixels[46:54, 55:105] = 20
    rgba = np.dstack([pixels, np.full((height, width), 255, np.uint8)])
    image = QImage(
        rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888
    ).copy()
    return image, background, pixels


@pytest.mark.parametrize("color", [Qt.GlobalColor.white, Qt.GlobalColor.red, Qt.GlobalColor.gray])
@pytest.mark.parametrize("rect", [QRect(0, 0, 200, 80), QRect(160, 90, 300, 120)])
def test_blur_preserves_flat_brightness_and_color(color, rect):
    image = QImage(640, 360, QImage.Format.Format_RGB32)
    image.fill(color)
    output = feathered_blur(image, rect, 24)
    np.testing.assert_array_equal(image_pixels(output), image_pixels(image.copy(rect)))


def test_blur_reduces_detail_with_continuous_feather_and_no_dark_tint():
    source = striped_image()
    rect = QRect(100, 120, 400, 100)
    pixels = image_pixels(feathered_blur(source, rect, 24))
    original = image_pixels(source.copy(rect))
    assert pixels[30:-30, 30:-30].std() < original.std() * 0.1
    assert abs(pixels.mean() - original.mean()) < 1
    np.testing.assert_array_equal(pixels[0], original[0])
    np.testing.assert_array_equal(pixels[-1], original[-1])
    np.testing.assert_array_equal(pixels[:, 0], original[:, 0])
    np.testing.assert_array_equal(pixels[:, -1], original[:, -1])
    # The first inner row blends gently instead of introducing a hard rectangle.
    assert np.abs(pixels[1].astype(float) - original[1]).max() < 3


def test_reconstruction_removes_text_pixels_and_restores_smooth_background():
    source, background, with_text = text_over_gradient()
    rect = QRect(40, 35, 80, 30)
    restored = image_pixels(reconstructed_background(source, rect, 24))
    expected = background[35:65, 40:120]
    damaged = with_text[35:65, 40:120]
    assert np.abs(restored.astype(float) - expected).mean() < 1
    assert np.abs(damaged.astype(float) - expected).mean() > 40
    assert restored.min() > 30  # Reconstruction must not introduce a black plate.


@pytest.fixture
def canvas(qtbot):
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(640, 360)
    canvas.frame_image = striped_image()
    canvas.interactive_mask_mode = True
    canvas.show()
    canvas.grab()
    return canvas


@pytest.mark.parametrize("corner", ["nw", "ne", "sw", "se"])
def test_each_corner_resizes_and_clamps_to_video(qtbot, canvas, corner):
    mask = MaskItem(x=0.2, y=0.3, width=0.4, height=0.3)
    canvas.set_masks([mask], mask.id)
    canvas.grab()
    rect = canvas._mask_rect(mask)
    start = {
        "nw": rect.topLeft(),
        "ne": rect.topRight(),
        "sw": rect.bottomLeft(),
        "se": rect.bottomRight(),
    }[corner]
    delta = QPoint(-100 if "w" in corner else 100, -70 if "n" in corner else 70)
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(canvas, start + delta)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=start + delta)
    assert mask.width > 0.4 and mask.height > 0.3
    assert 0 <= mask.x < mask.x + mask.width <= 1
    assert 0 <= mask.y < mask.y + mask.height <= 1
    saved = (mask.x, mask.y, mask.width, mask.height)
    canvas.resize(900, 650)  # A letterboxed preview must retain normalized geometry.
    canvas.grab()
    assert saved == (mask.x, mask.y, mask.width, mask.height)


def test_move_in_letterboxed_video_and_ignore_inactive_regions(qtbot, canvas):
    canvas.resize(640, 600)
    mask = MaskItem(x=0.2, y=0.3, width=0.4, height=0.3)
    inactive = MaskItem(x=0.2, y=0.3, width=0.4, height=0.3, start_ms=5000)
    canvas.set_masks([mask, inactive])
    canvas.grab()
    center = canvas._mask_rect(mask).center()
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=center)
    qtbot.mouseMove(canvas, center + QPoint(64, 36))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=center + QPoint(64, 36))
    assert canvas.active_mask_id == mask.id
    assert mask.x == pytest.approx(0.3) and mask.y == pytest.approx(0.4)
    assert inactive.x == 0.2 and inactive.y == 0.3
    canvas.set_current_time(6000)
    canvas.set_masks([inactive], inactive.id, 0)
    canvas.grab()
    assert not canvas.delete_mask_button.isVisible()


def test_single_click_add_drag_delete_restore_and_save(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("vkdub.media.process.MediaTools.detect", lambda self: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert not window.preview.btn_mask.isEnabled()
    window.project.video_path = tmp_path / "source.mp4"
    window._refresh()
    canvas = window.preview.video
    canvas.frame_image = striped_image()
    canvas.grab()
    original = image_pixels(canvas.grab().toImage())
    qtbot.mouseClick(window.preview.btn_mask, Qt.MouseButton.LeftButton)
    assert len(window.project.masks) == 1
    assert not any(d.isVisible() for d in window.findChildren(QDialog))
    mask = window.project.masks[0]
    canvas.grab()
    assert canvas.delete_mask_button.isVisible()
    center = canvas._mask_rect(mask).center()
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=center)
    qtbot.mouseMove(canvas, center + QPoint(0, -30))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=center + QPoint(0, -30))
    assert mask.y < 0.74 and window.dirty
    path = tmp_path / "blur.vkdub"
    assert window.save_to(path)
    saved = load_project(path)
    assert saved.masks[0].to_dict() == mask.to_dict()
    canvas.grab()
    qtbot.mouseClick(canvas.delete_mask_button, Qt.MouseButton.LeftButton)
    assert not window.project.masks and window.dirty
    np.testing.assert_array_equal(image_pixels(canvas.grab().toImage()), original)
    assert window.save_to(path) and not load_project(path).masks
    window.dirty = False


def test_real_ffmpeg_blur_timing_edges_and_multiple_regions():
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is not installed")
    source = image_pixels(striped_image(128, 96))
    masks = [
        MaskItem(
            mask_type="blur", x=0, y=0, width=1, height=1, start_ms=1000, end_ms=2000
        ),
        MaskItem(
            mask_type="blur",
            x=0.3,
            y=0.4,
            width=0.5,
            height=0.3,
            start_ms=1000,
            end_ms=2000,
        ),
    ]
    command = [
        str(ffmpeg),
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        "128x96",
        "-framerate",
        "1",
        "-i",
        "pipe:0",
        "-vf",
        build_ffmpeg_mask_filter(masks, 128, 96),
        "-frames:v",
        "4",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    result = subprocess.run(command, input=source.tobytes() * 4, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    frames = np.frombuffer(result.stdout, np.uint8).reshape(4, 96, 128, 3)
    assert np.abs(frames[0].astype(int) - source.astype(int)).max() <= 2
    assert np.abs(frames[3].astype(int) - source.astype(int)).max() <= 2
    np.testing.assert_array_equal(frames[1, 0], source[0])
    assert frames[1, 30:-30, 30:-30].std() < source.std() * 0.1
    assert abs(frames[1].mean() - source.mean()) < 1


def test_overlapping_regions_do_not_restore_sharp_pixels(canvas):
    canvas.interactive_mask_mode = False
    canvas.set_masks(
        [
            MaskItem(mask_type="blur", x=0, y=0, width=1, height=1, blur_strength=24),
            MaskItem(
                mask_type="blur", x=0.3, y=0.4, width=0.4, height=0.2, blur_strength=24
            ),
        ]
    )
    pixels = image_pixels(canvas.grab().toImage())
    assert pixels[140:220, 180:460].std() < 3


def test_real_ffmpeg_erase_reconstructs_background_without_text_or_black():
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is not installed")
    _, background, source = text_over_gradient()
    mask = MaskItem(
        mask_type="erase",
        x=40 / 160,
        y=35 / 100,
        width=80 / 160,
        height=30 / 100,
        start_ms=1000,
        end_ms=2000,
    )
    command = [
        str(ffmpeg),
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        "160x100",
        "-framerate",
        "1",
        "-i",
        "pipe:0",
        "-vf",
        build_ffmpeg_mask_filter([mask], 160, 100),
        "-frames:v",
        "4",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    result = subprocess.run(command, input=source.tobytes() * 4, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    frames = np.frombuffer(result.stdout, np.uint8).reshape(4, 100, 160, 3)
    expected = background[35:65, 40:120]
    original_error = np.abs(source[35:65, 40:120].astype(float) - expected).mean()
    restored_error = np.abs(frames[1, 35:65, 40:120].astype(float) - expected).mean()
    assert restored_error < 1
    assert restored_error < original_error * 0.05
    assert frames[1, 35:65, 40:120].min() > 30
    # delogo's format conversion can round unaffected RGB channels by 1-2 levels.
    assert np.abs(frames[0].astype(int) - source.astype(int)).max() <= 2
    assert np.abs(frames[3].astype(int) - source.astype(int)).max() <= 2
