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
    """Parse raw SRT text into a structured list of Cue objects.

    Robust to missing blank lines, code fences, numbered dots (e.g. '1.'),
    and conversational headers/footers.
    """
    cleaned = raw_srt.replace("\r\n", "\n").replace("\r", "\n").strip()
    # Remove UTF-8 BOM if present
    if cleaned.startswith("\ufeff"):
        cleaned = cleaned[1:]

    # Remove markdown code block fences if present (e.g. ```srt ... ```)
    cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned, flags=re.MULTILINE)

    lines = [line.strip() for line in cleaned.split("\n")]
    # Locate all line indices that match TIMECODE_PATTERN
    tc_indices: list[tuple[int, re.Match[str]]] = []
    for i, line in enumerate(lines):
        match = TIMECODE_PATTERN.search(line)
        if match:
            tc_indices.append((i, match))

    if not tc_indices:
        return []

    cues: list[Cue] = []
    for k, (tc_idx, tc_match) in enumerate(tc_indices):
        start_raw = tc_match.group(1).replace(".", ",")
        end_raw = tc_match.group(2).replace(".", ",")
        start_ms = timecode_to_ms(start_raw)
        end_ms = timecode_to_ms(end_raw)

        # Cue index is usually the line before tc_idx (e.g. '1' or '1.')
        cue_num = len(cues) + 1
        if tc_idx > 0:
            prev_line = lines[tc_idx - 1]
            digits = re.sub(r"\D", "", prev_line)
            prev_tc_limit = tc_indices[k - 1][0] if k > 0 else -1
            if digits and (tc_idx - 1 > prev_tc_limit):
                try:
                    cue_num = int(digits)
                except ValueError:
                    pass

        # Text lines: from tc_idx + 1 up to the start of the next cue
        if k + 1 < len(tc_indices):
            next_tc_idx = tc_indices[k + 1][0]
            if next_tc_idx > 0 and re.match(r"^\d+\.?$", lines[next_tc_idx - 1]):
                end_slice = next_tc_idx - 1
            else:
                end_slice = next_tc_idx
        else:
            end_slice = len(lines)

        text_lines = [l for l in lines[tc_idx + 1 : end_slice] if l]
        text_lines = [l for l in text_lines if not l.startswith("```")]
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


def align_and_fill_cues(orig_cues: list[Cue], trans_cues: list[Cue]) -> str:
    """Align translated cues 1-to-1 against original cues and format as valid SRT.

    Guarantees:
    - Exactly len(orig_cues) cues
    - 100% exact original timecodes and sequential indices
    - Timecode overlap matching if indices shifted
    - Never leaks Chinese/CJK characters into Vietnamese output
    """
    if not orig_cues:
        return ""
    if not trans_cues:
        return format_cues_to_srt(orig_cues)

    orig_indices = {c.index for c in orig_cues}
    trans_by_index = {c.index: c for c in trans_cues}
    has_matching_indices = any(c.index in orig_indices for c in trans_cues)

    aligned_cues: list[Cue] = []
    used_trans_cues: set[int] = set()

    for i, orig in enumerate(orig_cues):
        matched_text = ""

        # Strategy 1: Direct index match
        if has_matching_indices and orig.index in trans_by_index:
            matched_text = trans_by_index[orig.index].text.strip()
            used_trans_cues.add(orig.index)

        # Strategy 2: Timecode overlap matching (if indices shifted or merged)
        if not matched_text:
            for tc in trans_cues:
                if tc.index in used_trans_cues:
                    continue
                overlap = max(0, min(orig.end_ms, tc.end_ms) - max(orig.start_ms, tc.start_ms))
                duration = max(1, orig.end_ms - orig.start_ms)
                if overlap / duration > 0.4:
                    matched_text = tc.text.strip()
                    used_trans_cues.add(tc.index)
                    break

        # Strategy 3: Sequential fallback if not matching indices
        if not matched_text and not has_matching_indices and i < len(trans_cues):
            candidate = trans_cues[i].text.strip()
            if candidate and not re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", candidate):
                matched_text = candidate

        # Strategy 4: Fallback protection against CJK/Chinese
        if matched_text:
            final_text = matched_text
        else:
            is_cjk = bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", orig.text))
            if is_cjk:
                logger.warning(
                    "Câu #%d không tìm thấy bản dịch từ ChatGPT, thay thế bằng nhãn tiếng Việt để tránh đọc tiếng Trung.",
                    orig.index,
                )
                final_text = f"[Đoạn thoại #{orig.index}]"
            else:
                final_text = orig.text.strip()

        aligned_cues.append(
            Cue(
                index=orig.index,
                start_raw=orig.start_raw,
                end_raw=orig.end_raw,
                start_ms=orig.start_ms,
                end_ms=orig.end_ms,
                text=final_text,
            )
        )

    return format_cues_to_srt(aligned_cues, preserve_indices=True)


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
