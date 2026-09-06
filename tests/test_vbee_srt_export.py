"""Tests for automatic SRT generation for Vbee Dubbing integration."""

from pathlib import Path

import pytest

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.integrations.vbee.errors import VbeeValidationError
from vkdub.integrations.vbee.workflow import export_vbee_srt
from vkdub.services.srt_service import read_srt


def test_export_vbee_srt_content_and_encoding(tmp_path: Path) -> None:
    """Verify generated SRT has valid UTF-8, correct cues, timestamps and Vietnamese content."""
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"\x00" * 1024)

    lines = (
        ScriptLine.new(1000, 3500, "Xin chào các bạn đã quay trở lại."),
        ScriptLine.new(4000, 7250, "Hôm nay chúng ta sẽ tìm hiểu về Vbee Dubbing."),
        ScriptLine.new(8000, 11000, "Một giải pháp tự động hóa tuyệt vời."),
    )
    project = Project(
        video_path=video,
        target_language="vi",
        script=ScriptDocument(lines),
    )
    project.approve(True)

    output_dir = tmp_path / "export"
    srt_path = export_vbee_srt(project, output_dir)

    assert srt_path.is_file()
    assert srt_path.suffix == ".srt"

    # Verify UTF-8 encoding
    content = srt_path.read_text(encoding="utf-8")
    assert "Xin chào các bạn đã quay trở lại." in content
    assert "00:00:01,000 --> 00:00:03,500" in content
    assert "00:00:04,000 --> 00:00:07,250" in content
    assert "00:00:08,000 --> 00:00:11,000" in content

    # Verify round-trip parsing via read_srt
    parsed_doc = read_srt(srt_path)
    assert len(parsed_doc.lines) == 3
    assert parsed_doc.lines[0].text == "Xin chào các bạn đã quay trở lại."
    assert parsed_doc.lines[0].start_ms == 1000
    assert parsed_doc.lines[0].end_ms == 3500


def test_export_vbee_srt_unapproved_rejected(tmp_path: Path) -> None:
    """Verify exporting SRT refuses unapproved project script."""
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"\x00" * 1024)

    project = Project(
        video_path=video,
        target_language="vi",
        script=ScriptDocument((ScriptLine.new(0, 2000, "Câu chưa duyệt"),)),
    )
    assert project.is_approved is False

    with pytest.raises(VbeeValidationError, match="chưa được duyệt"):
        export_vbee_srt(project, tmp_path)
