"""Fast preview effects for obscuring text in video frames."""

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage


def _box_axis(pixels: NDArray[np.float32], radius: int, axis: int) -> NDArray[np.float32]:
    padding = [(0, 0), (0, 0), (0, 0)]
    padding[axis] = (radius, radius)
    extended = np.pad(pixels, padding, mode="edge")
    integral = np.cumsum(extended, axis=axis, dtype=np.float32)
    padding[axis] = (1, 0)
    integral = np.pad(integral, padding, mode="constant")
    size = 2 * radius + 1
    if axis == 0:
        return (integral[size:] - integral[:-size]) / np.float32(size)
    return (integral[:, size:] - integral[:, :-size]) / np.float32(size)


def feathered_blur(frame: QImage, rect: QRect, strength: int) -> QImage:
    """Return an opaque crop with a soft transition back to its source at every edge.

    Three separable box passes approximate Gaussian blur. Surrounding pixels supply
    context, and replicated frame boundaries avoid introducing black at video edges.
    Work at preview resolution; radius scales with height, like the render filter.
    """
    rect = rect.intersected(frame.rect())
    if frame.isNull() or rect.isEmpty():
        return QImage()
    radius = max(1, round(strength * frame.height() / 1080))
    context = rect.adjusted(-3 * radius, -3 * radius, 3 * radius, 3 * radius)
    context = context.intersected(frame.rect())
    crop = frame.copy(context).convertToFormat(QImage.Format.Format_RGBA8888)
    pixels = (
        np.frombuffer(crop.constBits(), dtype=np.uint8)
        .reshape(crop.height(), crop.bytesPerLine() // 4, 4)[:, : crop.width(), :3]
        .astype(np.float32)
    )
    blurred = pixels
    for _ in range(3):
        blurred = _box_axis(_box_axis(blurred, radius, 1), radius, 0)
    x, y = rect.x() - context.x(), rect.y() - context.y()
    width, height = rect.width(), rect.height()
    source = pixels[y : y + height, x : x + width]
    blurred = blurred[y : y + height, x : x + width]
    feather = max(1.0, min(width, height) * 0.16)
    xs = np.minimum(np.arange(width), np.arange(width)[::-1])
    ys = np.minimum(np.arange(height), np.arange(height)[::-1])
    alpha = np.clip(np.minimum(ys[:, None], xs[None, :]) / feather, 0, 1)
    alpha = (alpha * alpha * (3 - 2 * alpha))[:, :, None]
    output = np.empty((height, width, 4), dtype=np.uint8)
    output[:, :, :3] = np.rint(source + (blurred - source) * alpha).clip(0, 255)
    output[:, :, 3] = 255
    # Own the data after the numpy array is released.
    return QImage(output.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()


def reconstructed_background(frame: QImage, rect: QRect, strength: int) -> QImage:
    """Replace a selected area by smoothly extending pixels from its four sides.

    Unlike blur, this does not reuse any pixels from inside the rectangle, so text
    cannot remain visible as a soft silhouette. The render path uses FFmpeg's
    purpose-built ``delogo`` filter; this lightweight implementation keeps the
    interactive preview responsive while following the same boundary-inpainting
    principle.
    """
    rect = rect.intersected(frame.rect())
    if frame.isNull() or rect.isEmpty():
        return QImage()

    converted = frame.convertToFormat(QImage.Format.Format_RGBA8888)
    frame_pixels = (
        np.frombuffer(converted.constBits(), dtype=np.uint8)
        .reshape(converted.height(), converted.bytesPerLine() // 4, 4)[:, : converted.width(), :3]
        .astype(np.float32)
    )
    x0, y0 = rect.x(), rect.y()
    width, height = rect.width(), rect.height()
    x1, y1 = x0 + width, y0 + height
    band = max(2, round(strength * frame.height() / 1080))

    top = (
        frame_pixels[max(0, y0 - band) : y0, x0:x1].mean(axis=0)
        if y0 > 0
        else None
    )
    bottom = (
        frame_pixels[y1 : min(frame.height(), y1 + band), x0:x1].mean(axis=0)
        if y1 < frame.height()
        else None
    )
    left = (
        frame_pixels[y0:y1, max(0, x0 - band) : x0].mean(axis=1)
        if x0 > 0
        else None
    )
    right = (
        frame_pixels[y0:y1, x1 : min(frame.width(), x1 + band)].mean(axis=1)
        if x1 < frame.width()
        else None
    )

    # A selection can touch a frame edge. Mirror the available opposite boundary
    # so reconstruction still works without adding black or transparent pixels.
    if top is None:
        top = bottom
    if bottom is None:
        bottom = top
    if left is None:
        left = right
    if right is None:
        right = left
    if top is None and left is not None and right is not None:
        top = np.linspace(left[0], right[0], width, dtype=np.float32)
        bottom = np.linspace(left[-1], right[-1], width, dtype=np.float32)
    if left is None and top is not None and bottom is not None:
        left = np.linspace(top[0], bottom[0], height, dtype=np.float32)
        right = np.linspace(top[-1], bottom[-1], height, dtype=np.float32)
    if top is None or bottom is None or left is None or right is None:
        # There is no outside context only when the selection covers the full frame.
        return feathered_blur(frame, rect, strength)

    smooth_radius = max(1, min(band, max(1, min(width, height) // 6)))
    top = _box_axis(top[None, :, :], smooth_radius, 1)[0]
    bottom = _box_axis(bottom[None, :, :], smooth_radius, 1)[0]
    left = _box_axis(left[:, None, :], smooth_radius, 0)[:, 0]
    right = _box_axis(right[:, None, :], smooth_radius, 0)[:, 0]

    # Inverse distances make every edge meet the pixels immediately outside it,
    # while the middle becomes an even blend of all surrounding content.
    xs = (np.arange(width, dtype=np.float32) + 1.0) / np.float32(width + 1)
    ys = (np.arange(height, dtype=np.float32) + 1.0) / np.float32(height + 1)
    weight_top = 1.0 / ys[:, None]
    weight_bottom = 1.0 / (1.0 - ys[:, None])
    weight_left = 1.0 / xs[None, :]
    weight_right = 1.0 / (1.0 - xs[None, :])
    total = weight_top + weight_bottom + weight_left + weight_right
    filled = (
        top[None, :, :] * weight_top[:, :, None]
        + bottom[None, :, :] * weight_bottom[:, :, None]
        + left[:, None, :] * weight_left[:, :, None]
        + right[:, None, :] * weight_right[:, :, None]
    ) / total[:, :, None]

    output = np.empty((height, width, 4), dtype=np.uint8)
    output[:, :, :3] = np.rint(filled).clip(0, 255)
    output[:, :, 3] = 255
    return QImage(output.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
