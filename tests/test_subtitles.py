from uuid import uuid4

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage

from vkdub.domain.project import Project
from vkdub.domain.script import ScriptDocument, ScriptLine
from vkdub.domain.subtitle import (
    SubtitleStyle,
    color_to_ass,
    format_ass_time,
    to_ass_script,
)
from vkdub.services.subtitle_service import (
    export_ass,
    export_srt,
    load_presets,
    subtitle_for_time,
)
from vkdub.ui.subtitle_style_dialog import SubtitleStyleDialog
from vkdub.ui.video_canvas import VideoCanvas


def test_color_to_ass():
    assert color_to_ass("#FFFFFF", 1.0) == "&H00FFFFFF"
    assert color_to_ass("#000000", 1.0) == "&H00000000"
    assert color_to_ass("#FF0000", 1.0) == "&H000000FF"
    assert color_to_ass("#00FF00", 1.0) == "&H0000FF00"
    assert color_to_ass("#0000FF", 1.0) == "&H00FF0000"
    ass_alpha = color_to_ass("#000000", 0.5)
    assert ass_alpha.startswith("&H7F") or ass_alpha.startswith("&H80")


def test_format_ass_time():
    assert format_ass_time(0) == "0:00:00.00"
    assert format_ass_time(1500) == "0:00:01.50"
    assert format_ass_time(65430) == "0:01:05.43"
    assert format_ass_time(3665120) == "1:01:05.12"


def test_presets_loaded_correctly():
    presets = load_presets()
    expected = ["Minimal", "YouTube", "TikTok", "Movie", "Bold Caption"]
    for name in expected:
        assert name in presets
        preset = presets[name]
        assert isinstance(preset, SubtitleStyle)
        assert preset.font_family != ""
        assert preset.font_size > 0


def test_to_ass_script_and_export_ass(tmp_path):
    lines = (
        ScriptLine(id=str(uuid4()), start_ms=0, end_ms=2000, text="Xin chào thế giới"),
        ScriptLine(id=str(uuid4()), start_ms=2500, end_ms=5000, text="Dòng thứ hai\nngắt dòng"),
    )
    script = ScriptDocument(lines=lines)
    style = SubtitleStyle(name="TikTok", font_size=48, bold=True)
    ass_content = to_ass_script(script, style, 1920, 1080)

    assert "[Script Info]" in ass_content
    assert "PlayResX: 1920" in ass_content
    assert "PlayResY: 1080" in ass_content
    assert "[V4+ Styles]" in ass_content
    assert "Style: Default" in ass_content
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Xin chào thế giới" in ass_content
    assert (
        "Dialogue: 0,0:00:02.50,0:00:05.00,Default,,0,0,0,,Dòng thứ hai\\Nngắt dòng" in ass_content
    )

    project = Project(script=script, subtitle_style=style)
    ass_file = tmp_path / "test.ass"
    export_ass(project, ass_file)
    assert ass_file.is_file()
    assert ass_file.read_text(encoding="utf-8-sig").startswith("[Script Info]")


def test_export_ass_uses_preview_reference_canvas_for_non_hd_video(tmp_path):
    line = ScriptLine(id=str(uuid4()), start_ms=0, end_ms=1000, text="Đúng vị trí")
    project = Project(
        script=ScriptDocument((line,)),
        subtitle_style=SubtitleStyle(background_box=True, margin_bottom=163),
    )
    ass_file = tmp_path / "position.ass"
    export_ass(project, ass_file)
    content = ass_file.read_text(encoding="utf-8-sig")
    assert "PlayResX: 1920" in content
    assert "PlayResY: 1080" in content
    assert ",3,3.0,1.5,2,30,30,163,1" in content


def test_export_srt(tmp_path):
    lines = (
        ScriptLine(id=str(uuid4()), start_ms=0, end_ms=2000, text="Dòng một"),
        ScriptLine(id=str(uuid4()), start_ms=2500, end_ms=5000, text="Dòng hai"),
    )
    script = ScriptDocument(lines=lines)
    project = Project(script=script)
    srt_file = tmp_path / "test.srt"
    export_srt(project, srt_file)
    assert srt_file.is_file()
    content = srt_file.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:02,000\nDòng một" in content


def test_subtitle_for_time():
    lines = (
        ScriptLine(id=str(uuid4()), start_ms=1000, end_ms=3000, text="Đoạn 1"),
        ScriptLine(id=str(uuid4()), start_ms=4000, end_ms=6000, text="Đoạn 2"),
    )
    script = ScriptDocument(lines=lines)
    assert subtitle_for_time(script, 500) is None
    assert subtitle_for_time(script, 1000) == "Đoạn 1"
    assert subtitle_for_time(script, 2500) == "Đoạn 1"
    assert subtitle_for_time(script, 3000) == "Đoạn 1"
    assert subtitle_for_time(script, 3500) is None
    assert subtitle_for_time(script, 5000) == "Đoạn 2"
    assert subtitle_for_time(script, 7000) is None
    assert subtitle_for_time(None, 1000) is None


def test_video_canvas_paint_subtitle(qtbot):
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(640, 360)

    # Frame image
    img = QImage(640, 360, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.black)
    canvas.frame_image = img

    style = SubtitleStyle(
        font_size=32,
        bold=True,
        background_box=True,
        background_color="#000000",
        background_opacity=0.7,
        outline_width=2.0,
        shadow_offset=2.0,
    )
    canvas.set_subtitle("Đây là phụ đề thử nghiệm trực tiếp trên video canvas", style)
    canvas.subtitle_edit_mode = True

    # Force paintEvent
    canvas.show()
    qtbot.wait(10)
    canvas.repaint()
    assert canvas.current_subtitle == "Đây là phụ đề thử nghiệm trực tiếp trên video canvas"
    assert canvas.subtitle_style == style
    assert not canvas._subtitle_rect.isEmpty()
    with qtbot.waitSignal(canvas.subtitle_margin_changed, timeout=1000) as changed:
        qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=canvas._subtitle_rect.center())
        qtbot.mouseMove(canvas, canvas._subtitle_rect.center() + QPoint(0, 20))
        qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton)
    assert changed.args[0] < style.margin_bottom


def test_subtitle_style_dialog_presets_and_get_style(qtbot):
    dialog = SubtitleStyleDialog()
    qtbot.addWidget(dialog)

    initial_style = SubtitleStyle(
        name="YouTube",
        font_family="Arial",
        font_size=44,
        bold=True,
        italic=False,
        text_color="#FFFFFF",
    )
    dialog.set_current_style(initial_style)
    assert dialog.preset_combo.currentText() == "YouTube"
    assert dialog.size_slider.value() == 44

    # Switch to TikTok preset
    dialog.preset_combo.setCurrentText("TikTok")
    style = dialog.get_style()
    assert style.name == "TikTok"
    assert style.bold is True
    assert style.text_color == "#FFE600"
