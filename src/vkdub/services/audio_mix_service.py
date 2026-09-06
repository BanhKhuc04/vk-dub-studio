import os
import subprocess
import tempfile
import wave
from pathlib import Path

from vkdub.domain.project import Project

TARGET_SAMPLE_RATE = 24000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # 16-bit PCM


def _normalize_wav(
    source: Path,
    target: Path,
    ffmpeg: str,
    sample_rate: int = TARGET_SAMPLE_RATE,
    channels: int = TARGET_CHANNELS,
    tempo: float = 1.0,
) -> None:
    """Convert any audio file to the target WAV format using FFmpeg."""
    command = [
            ffmpeg,
            "-y",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
    ]
    if tempo > 1.001:
        factors: list[float] = []
        remaining = tempo
        while remaining > 2.0:
            factors.append(2.0)
            remaining /= 2.0
        factors.append(remaining)
        command.extend(["-af", ",".join(f"atempo={factor:.6f}" for factor in factors)])
    command.extend(
        [
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-sample_fmt",
            "s16",
            "-f",
            "wav",
            str(target),
        ]
    )
    run = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if run.returncode or not target.is_file():
        detail = run.stderr.strip().splitlines()[-1] if run.stderr.strip() else "FFmpeg thất bại."
        raise ValueError(f"Không chuyển đổi được file WAV: {detail}")


def _wav_info(path: Path) -> tuple[int, int, int, int]:
    with wave.open(str(path), "rb") as source:
        return (
            source.getframerate(),
            source.getnchannels(),
            source.getsampwidth(),
            source.getnframes(),
        )


def voice_slot_duration_ms(project: Project, index: int, total_duration_ms: int) -> int:
    """Return the non-overlapping timeline space available to one voice sentence."""
    assert project.script is not None
    line = project.script.lines[index]
    next_start = (
        project.script.lines[index + 1].start_ms
        if index + 1 < len(project.script.lines)
        else total_duration_ms
    )
    slot_end = min(line.end_ms, next_start, total_duration_ms)
    return max(1, slot_end - line.start_ms)


def fit_voice_wav(
    source: Path,
    target: Path,
    ffmpeg: str | None,
    max_duration_ms: int,
    sample_rate: int | None = None,
) -> int:
    """Create a mono PCM WAV that fits its timeline slot without changing pitch."""
    rate, channels, width, frames = _wav_info(source)
    sample_rate = rate if sample_rate is None and channels == 1 and width == 2 else sample_rate
    sample_rate = sample_rate or TARGET_SAMPLE_RATE
    duration_ms = round(frames * 1000 / rate)
    tempo = max(1.0, duration_ms / max(1, max_duration_ms))
    needs_conversion = (rate, channels, width) != (sample_rate, TARGET_CHANNELS, 2)
    if needs_conversion or tempo > 1.001:
        if not ffmpeg:
            raise ValueError(
                f"Voice {source.name} cần FFmpeg để chuẩn hóa âm thanh và khớp thời gian."
            )
        _normalize_wav(source, target, ffmpeg, sample_rate, TARGET_CHANNELS, tempo)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    out_rate, _, _, out_frames = _wav_info(target)
    return min(max_duration_ms, round(out_frames * 1000 / out_rate))


def _project_sample_rate(project: Project) -> int:
    """Keep a shared native voice rate when every current asset uses it."""
    formats: set[tuple[int, int, int]] = set()
    for asset in project.current_voices().values():
        try:
            rate, channels, width, _ = _wav_info(asset.output_path)
        except (OSError, EOFError, wave.Error):
            return TARGET_SAMPLE_RATE
        formats.add((rate, channels, width))
    if len(formats) == 1:
        rate, channels, width = next(iter(formats))
        if channels == TARGET_CHANNELS and width == TARGET_SAMPLE_WIDTH:
            return rate
    return TARGET_SAMPLE_RATE


def build_speech_track_wav(
    project: Project,
    output_path: Path,
    total_duration_ms: int,
    ffmpeg: str | None = None,
) -> Path:
    """Combine per-segment voice assets into a single synchronized 24kHz mono WAV track."""
    if project.script is None:
        raise ValueError("Chưa có kịch bản.")
    current_voices = project.current_voices()
    if len(current_voices) != len(project.script.lines):
        raise ValueError("Chưa tạo đủ voice cho tất cả các câu kịch bản.")

    sample_rate = _project_sample_rate(project)
    channels = TARGET_CHANNELS
    sample_width = TARGET_SAMPLE_WIDTH

    total_samples = int(total_duration_ms * sample_rate / 1000)
    # 16-bit signed integer buffer initialized to zero (silence)
    raw_buffer = bytearray(total_samples * sample_width * channels)

    tmp_dir = None
    try:
        for index, line in enumerate(project.script.lines):
            asset = current_voices[line.id]
            if not asset.output_path.is_file():
                raise ValueError(f"Không tìm thấy voice câu {index + 1}: {asset.output_path.name}")

            start_sample = int(line.start_ms * sample_rate / 1000)
            slot_ms = voice_slot_duration_ms(project, index, total_duration_ms)
            try:
                rate, source_channels, source_width, source_frames = _wav_info(asset.output_path)
                source_duration_ms = round(source_frames * 1000 / rate)
                if (
                    (rate, source_channels, source_width) == (sample_rate, channels, sample_width)
                    and source_duration_ms <= slot_ms
                ):
                    with wave.open(str(asset.output_path), "rb") as source_wav:
                        frames = source_wav.readframes(source_frames)
                else:
                    if tmp_dir is None:
                        tmp_dir = tempfile.TemporaryDirectory(prefix="vkdub_wav_norm_")
                    normalized = Path(tmp_dir.name) / f"norm_{index:04}.wav"
                    fit_voice_wav(
                        asset.output_path, normalized, ffmpeg, slot_ms, sample_rate
                    )
                    with wave.open(str(normalized), "rb") as normalized_wav:
                        frames = normalized_wav.readframes(normalized_wav.getnframes())
                max_bytes = int(slot_ms * sample_rate / 1000) * sample_width * channels
                frames = frames[:max_bytes]
                offset = start_sample * sample_width * channels
                end_offset = min(len(raw_buffer), offset + len(frames))
                copy_len = end_offset - offset
                if copy_len > 0:
                    raw_buffer[offset : offset + copy_len] = frames[:copy_len]
            except (OSError, EOFError, wave.Error, ValueError) as exc:
                raise ValueError(f"Không ghép được voice câu {index + 1}: {exc}") from exc
    finally:
        if tmp_dir is not None:
            try:
                tmp_dir.cleanup()
            except Exception:
                pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as out_wf:
        out_wf.setnchannels(channels)
        out_wf.setsampwidth(sample_width)
        out_wf.setframerate(sample_rate)
        out_wf.writeframes(raw_buffer)

    return output_path


def build_audio_mix_filter(
    original_volume: float = 0.15,
    voice_volume: float = 1.0,
    has_original_audio: bool = True,
) -> str:
    """Generate FFmpeg audio filter complex graph for mixing original audio with voice track.

    Inputs:
    [0:a] = original video audio
    [1:a] = generated speech track WAV
    """
    if not has_original_audio or original_volume <= 0.001:
        # Original audio muted or not present, only use voice
        return f"[1:a]volume={voice_volume:.2f}[aout]"

    filter_graph = (
        f"[0:a]volume={original_volume:.2f}[aorig];"
        f"[1:a]volume={voice_volume:.2f}[avoice];"
        f"[aorig][avoice]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    return filter_graph
