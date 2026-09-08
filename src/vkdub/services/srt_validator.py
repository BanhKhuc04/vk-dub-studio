"""SRT Validation and Repair Service for VK Dub Studio.

Validates translated SRT files against original SRT files according to strict rules:
1. Cue count must match exactly.
2. Timecodes must match original timecodes.
3. No empty cues allowed.
4. Valid SRT formatting.
5. Automatic repair heuristics for common LLM formatting drifts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import NamedTuple

logger = logging.getLogger("vkdub.srt_validator")

# Regex to parse standard SRT timecode line: 00:00:01,000 --> 00:00:04,500
TIMECODE_PATTERN = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})"
)


@dataclass
class Cue:
    index: int
    start_raw: str
    end_raw: str
    text: str
    start_ms: int = 0
    end_ms: int = 0


class ValidationResult(NamedTuple):
    is_valid: bool
    errors: list[str]
    repaired_srt: str | None = None
    cue_count: int = 0


def timecode_to_ms(tc: str) -> int:
    """Convert HH:MM:SS,mmm or HH:MM:SS.mmm to milliseconds."""
    tc = tc.replace(".", ",")
    parts = tc.split(":")
    if len(parts) != 3:
        return 0
    hours = int(parts[0])
    minutes = int(parts[1])
    sec_parts = parts[2].split(",")
    seconds = int(sec_parts[0])
    millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + millis


def ms_to_timecode(ms: int) -> str:
    """Convert milliseconds to standard SRT timecode HH:MM:SS,mmm."""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_cues(raw_srt: str) -> list[Cue]:
    """Parse raw SRT text into a structured list of Cue objects."""
    cleaned = raw_srt.replace("\r\n", "\n").replace("\r", "\n").strip()
    # Remove UTF-8 BOM if present
    if cleaned.startswith("\ufeff"):
        cleaned = cleaned[1:]

    # Remove markdown code block fences if present (e.g. ```srt ... ```)
    cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
    cleaned = re.sub(r"\n```$", "", cleaned)

    blocks = re.split(r"\n\s*\n+", cleaned)
    cues: list[Cue] = []

    for block in blocks:
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if not lines:
            continue

        # Find line containing timecode
        tc_index = -1
        tc_match = None
        for idx, line in enumerate(lines):
            match = TIMECODE_PATTERN.search(line)
            if match:
                tc_index = idx
                tc_match = match
                break

        if not tc_match or tc_index == -1:
            continue

        start_raw = tc_match.group(1).replace(".", ",")
        end_raw = tc_match.group(2).replace(".", ",")
        start_ms = timecode_to_ms(start_raw)
        end_ms = timecode_to_ms(end_raw)

        # Cue number is usually the line before timecode
        cue_num = len(cues) + 1
        if tc_index > 0:
            try:
                cue_num = int(re.sub(r"\D", "", lines[0]) or str(len(cues) + 1))
            except ValueError:
                pass

        # Cue text is all lines after timecode
        text_lines = lines[tc_index + 1 :]
        text = " ".join(text_lines).strip()

        cues.append(
            Cue(
                index=cue_num,
                start_raw=start_raw,
                end_raw=end_raw,
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )

    return cues


def format_cues_to_srt(cues: list[Cue], preserve_indices: bool = False) -> str:
    """Format a list of Cues back into standard SRT string."""
    output = []
    for idx, cue in enumerate(cues, 1):
        num = cue.index if preserve_indices else idx
        output.append(str(num))
        output.append(f"{cue.start_raw} --> {cue.end_raw}")
        output.append(cue.text)
        output.append("")
    return "\n".join(output)


def validate_and_repair_srt(
    original_srt: str,
    translated_srt: str,
    auto_repair_timecodes: bool = True,
) -> ValidationResult:
    """Validate translated SRT against original SRT and apply repairs if possible.

    Validation Rules:
    - original cue count == translated cue count
    - original timecodes == translated timecodes
    - no empty cues
    - valid SRT format
    """
    errors: list[str] = []
    orig_cues = parse_cues(original_srt)
    trans_cues = parse_cues(translated_srt)

    if not orig_cues:
        return ValidationResult(
            is_valid=False,
            errors=["File phụ đề gốc không chứa câu phụ đề hợp lệ."],
            cue_count=0,
        )

    if not trans_cues:
        return ValidationResult(
            is_valid=False,
            errors=["Không trích xuất được câu phụ đề nào từ kết quả ChatGPT."],
            cue_count=0,
        )

    # 1. Cue count check
    if len(trans_cues) != len(orig_cues):
        errors.append(
            f"Số lượng câu không khớp: Gốc có {len(orig_cues)} câu, "
            f"bản dịch ChatGPT có {len(trans_cues)} câu."
        )

    # 2. Check for empty cues
    empty_cues = [c.index for c in trans_cues if not c.text.strip()]
    if empty_cues:
        errors.append(f"Có {len(empty_cues)} câu bị trống nội dung: câu {empty_cues[:5]}")

    # 3. Timecode check and auto-repair
    repaired_cues: list[Cue] = []
    timecode_drifts = 0

    if len(trans_cues) == len(orig_cues):
        for i, (orig, trans) in enumerate(zip(orig_cues, trans_cues, strict=True)):
            # Check if timecodes match
            time_diff = abs(orig.start_ms - trans.start_ms) + abs(orig.end_ms - trans.end_ms)
            if time_diff > 100:  # more than 100ms difference
                timecode_drifts += 1

            # Apply strict timecode snapping to original timecodes
            repaired_cue = Cue(
                index=i + 1,
                start_raw=orig.start_raw if auto_repair_timecodes else trans.start_raw,
                end_raw=orig.end_raw if auto_repair_timecodes else trans.end_raw,
                start_ms=orig.start_ms if auto_repair_timecodes else trans.start_ms,
                end_ms=orig.end_ms if auto_repair_timecodes else trans.end_ms,
                text=trans.text.strip(),
            )
            repaired_cues.append(repaired_cue)

        if timecode_drifts > 0:
            if auto_repair_timecodes:
                logger.info(
                    "Tự động đồng bộ lại %d mốc thời gian theo file SRT gốc.",
                    timecode_drifts,
                )
            else:
                errors.append(f"Có {timecode_drifts} câu bị lệch mốc thời gian so với bản gốc.")

    repaired_str = format_cues_to_srt(repaired_cues) if repaired_cues else None
    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        repaired_srt=repaired_str,
        cue_count=len(trans_cues),
    )
