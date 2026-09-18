"""Hardware encoder detection and parameter configuration for FFmpeg.

Actively probes available GPU hardware encoders (NVENC, QSV, AMF) using a
1-frame test to guarantee runtime operational capability before falling back
to CPU software encoding (libx264 / libx265).
"""

import os
import subprocess
from typing import Final

from vkdub.media.process import find_tool

# Encoder parameter definitions targeting visually lossless quality (CRF 17-18 equivalent)
ENCODER_PARAMS: Final[dict[str, list[str]]] = {
    # NVIDIA NVENC
    "h264_nvenc": ["-preset", "p5", "-rc", "vbr", "-cq", "18", "-b:v", "0", "-pix_fmt", "yuv420p"],
    "hevc_nvenc": ["-preset", "p5", "-rc", "vbr", "-cq", "18", "-b:v", "0", "-pix_fmt", "yuv420p"],
    # Intel QSV
    "h264_qsv": ["-global_quality", "18", "-preset", "medium", "-pix_fmt", "yuv420p"],
    "hevc_qsv": ["-global_quality", "18", "-preset", "medium", "-pix_fmt", "yuv420p"],
    # AMD AMF
    "h264_amf": [
        "-rc",
        "cqp",
        "-qp_i",
        "18",
        "-qp_p",
        "18",
        "-qp_b",
        "18",
        "-quality",
        "quality",
        "-pix_fmt",
        "yuv420p",
    ],
    "hevc_amf": [
        "-rc",
        "cqp",
        "-qp_i",
        "18",
        "-qp_p",
        "18",
        "-qp_b",
        "18",
        "-quality",
        "quality",
        "-pix_fmt",
        "yuv420p",
    ],
    # CPU Software fallback
    "libx264": ["-crf", "18", "-preset", "faster", "-pix_fmt", "yuv420p"],
    "libx265": ["-crf", "18", "-preset", "faster", "-pix_fmt", "yuv420p"],
}

# In-memory caches to avoid redundant child process executions
_PROBE_CACHE: dict[tuple[str, str], bool] = {}
_RESOLVED_CACHE: dict[tuple[str, str], tuple[str, list[str]]] = {}


def clear_cache() -> None:
    """Clear in-memory probe and resolution caches."""
    _PROBE_CACHE.clear()
    _RESOLVED_CACHE.clear()


def get_encoder_params(encoder: str) -> list[str]:
    """Return quality parameters for the specified encoder."""
    return list(ENCODER_PARAMS.get(encoder, ["-crf", "18", "-pix_fmt", "yuv420p"]))


def probe_encoder(ffmpeg_exe: str, encoder: str, timeout: float = 3.0) -> bool:
    """Run an active 1-frame probe test with FFmpeg to verify that the encoder

    actually initializes and completes without hardware or driver errors.
    """
    key = (ffmpeg_exe, encoder)
    if key in _PROBE_CACHE:
        return _PROBE_CACHE[key]

    # CPU encoders are always considered operational if compiled
    if encoder.startswith("libx"):
        _PROBE_CACHE[key] = True
        return True

    cmd = [
        ffmpeg_exe,
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=s=256x256:d=0.04",
        "-c:v",
        encoder,
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]

    try:
        creationflags = 0x08000000 if os.name == "nt" else 0
        res = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            creationflags=creationflags,
        )
        is_ok = res.returncode == 0
    except Exception:
        is_ok = False

    _PROBE_CACHE[key] = is_ok
    return is_ok


def resolve_best_encoder(
    ffmpeg_exe: str | None = None, codec_family: str = "h264"
) -> tuple[str, list[str]]:
    """Determine the optimal video encoder based on active hardware probe.

    Priority order:
    1. NVIDIA NVENC (h264_nvenc / hevc_nvenc)
    2. Intel QSV (h264_qsv / hevc_qsv)
    3. AMD AMF (h264_amf / hevc_amf)
    4. CPU fallback (libx264 / libx265)
    """
    exe = ffmpeg_exe or find_tool("ffmpeg")
    if not exe:
        # If ffmpeg is completely absent, return software fallback
        fallback = "libx264" if codec_family.lower() == "h264" else "libx265"
        return fallback, get_encoder_params(fallback)
    fam = codec_family.lower()
    normalized_family = "hevc" if ("265" in fam or "hevc" in fam) else "h264"
    cache_key = (exe, normalized_family)
    if cache_key in _RESOLVED_CACHE:
        return _RESOLVED_CACHE[cache_key]

    if normalized_family == "h264":
        candidates = ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"]
        fallback = "libx264"
    else:
        candidates = ["hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265"]
        fallback = "libx265"

    for candidate in candidates:
        if probe_encoder(exe, candidate):
            result = (candidate, get_encoder_params(candidate))
            _RESOLVED_CACHE[cache_key] = result
            return result

    result = (fallback, get_encoder_params(fallback))
    _RESOLVED_CACHE[cache_key] = result
    return result


class HardwareEncoderDetector:
    """Encapsulates hardware encoder discovery and capability detection."""

    def __init__(self, ffmpeg_exe: str | None = None) -> None:
        self.ffmpeg_exe = ffmpeg_exe or find_tool("ffmpeg")

    def probe(self, encoder: str) -> bool:
        """Probe whether a specific encoder works on the current system."""
        if not self.ffmpeg_exe:
            return encoder.startswith("libx")
        return probe_encoder(self.ffmpeg_exe, encoder)

    def get_params(self, encoder: str) -> list[str]:
        """Get optimal encoding flags for an encoder."""
        return get_encoder_params(encoder)

    def detect(self, codec_family: str = "h264") -> tuple[str, list[str]]:
        """Detect the best operational encoder and return (encoder_name, encoder_params)."""
        return resolve_best_encoder(self.ffmpeg_exe, codec_family)

    def is_hardware_accelerated(self, encoder: str) -> bool:
        """Return True if the encoder is GPU hardware-accelerated."""
        return not encoder.startswith("libx")
