"""Unit tests for srt_validator.py."""

from vkdub.services.srt_validator import (
    ms_to_timecode,
    timecode_to_ms,
    validate_and_repair_srt,
)

ORIGINAL_SRT = """1
00:00:01,000 --> 00:00:03,500
Hello, this is a test.

2
00:00:04,000 --> 00:00:07,250
Welcome to VK Dub Studio.

3
00:00:08,100 --> 00:00:10,000
Automating video dubbing.
"""

TRANSLATED_PERFECT_SRT = """1
00:00:01,000 --> 00:00:03,500
Xin chào, đây là một bài kiểm tra.

2
00:00:04,000 --> 00:00:07,250
Chào mừng bạn đến với VK Dub Studio.

3
00:00:08,100 --> 00:00:10,000
Tự động hóa lồng tiếng video.
"""

TRANSLATED_WITH_MARKDOWN_AND_DRIFT = """```srt
1.
00:00:01.050 --> 00:00:03.480
Xin chào, đây là một bài kiểm tra.

2.
00:00:04.020 --> 00:00:07.200
Chào mừng bạn đến với VK Dub Studio.

3.
00:00:08.100 --> 00:00:10.000
Tự động hóa lồng tiếng video.
```"""

TRANSLATED_MISSING_CUE = """1
00:00:01,000 --> 00:00:03,500
Xin chào, đây là một bài kiểm tra.

2
00:00:04,000 --> 00:00:07,250
Chào mừng bạn đến với VK Dub Studio.
"""

TRANSLATED_EMPTY_CUE = """1
00:00:01,000 --> 00:00:03,500
Xin chào, đây là một bài kiểm tra.

2
00:00:04,000 --> 00:00:07,250


3
00:00:08,100 --> 00:00:10,000
Tự động hóa lồng tiếng video.
"""


def test_timecode_conversions():
    assert timecode_to_ms("00:00:01,500") == 1500
    assert timecode_to_ms("01:02:03,456") == 3600000 + 120000 + 3000 + 456
    assert ms_to_timecode(1500) == "00:00:01,500"


def test_validation_perfect_match():
    res = validate_and_repair_srt(ORIGINAL_SRT, TRANSLATED_PERFECT_SRT)
    assert res.is_valid is True
    assert len(res.errors) == 0
    assert res.cue_count == 3


def test_validation_auto_repair_markdown_and_drift():
    res = validate_and_repair_srt(
        ORIGINAL_SRT, TRANSLATED_WITH_MARKDOWN_AND_DRIFT, auto_repair_timecodes=True
    )
    assert res.is_valid is True
    assert res.cue_count == 3
    assert res.repaired_srt is not None
    # Verify repaired timecode snapped back to exact original
    assert "00:00:01,000 --> 00:00:03,500" in res.repaired_srt


def test_validation_missing_cue_fails():
    res = validate_and_repair_srt(ORIGINAL_SRT, TRANSLATED_MISSING_CUE)
    assert res.is_valid is False
    assert any("Số lượng câu không khớp" in err for err in res.errors)


def test_validation_empty_cue_fails():
    res = validate_and_repair_srt(ORIGINAL_SRT, TRANSLATED_EMPTY_CUE)
    assert res.is_valid is False
    assert any("trống nội dung" in err for err in res.errors)
