"""FFmpeg rendering engine for Auto Video Generator."""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from kappak.modules.auto_video.domain import AutoVideoProject, SceneSegment
from kappak.modules.auto_video.templates import (
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
    build_template_filtergraph,
)
from vkdub.media.hardware import resolve_best_encoder
from vkdub.media.process import find_tool
from vkdub.services.discord_notifier import send_discord_message
from vkdub.utils.paths import workspace_root

logger = logging.getLogger("kappak.modules.auto_video.renderer")


def generate_ass_subtitles(scenes: list[SceneSegment], output_path: Path) -> Path:
    """Generate styled Advanced SubStation Alpha (.ass) subtitles for TikTok/Reels."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""[Script Info]
Title: Auto Video Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: {TARGET_WIDTH}
PlayResY: {TARGET_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTokStyle,Arial,58,&H0000FFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,3,2,60,60,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds - int(seconds)) * 100))
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    events = []
    current_t = 0.0
    for scene in scenes:
        start_t = current_t
        dur = scene.duration_sec or 3.0
        end_t = start_t + dur
        current_t = end_t

        text = scene.text.strip().replace("\n", " ")
        if text:
            events.append(
                f"Dialogue: 0,{fmt_time(start_t)},{fmt_time(end_t)},TikTokStyle,,0,0,0,,{text}\n"
            )

    output_path.write_text(header + "".join(events), encoding="utf-8")
    return output_path


class AutoVideoRenderer:
    """Engine executing full multi-scene 9:16 video assembly."""

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or (workspace_root() / "auto_video" / "renders")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg = find_tool("ffmpeg")
        if not self.ffmpeg:
            raise RuntimeError("Không tìm thấy công cụ FFmpeg trên hệ thống.")

    def render_scene_video(
        self,
        scene: SceneSegment,
        template_id: str,
        output_file: Path,
        hook_text: str = "",
    ) -> Path:
        """Render a single scene segment into 9:16 target resolution video."""
        dur = max(1.5, scene.duration_sec or 3.0)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        asset_path = Path(scene.asset_path) if scene.asset_path else None
        encoder_name, enc_params = resolve_best_encoder(self.ffmpeg, "h264")
        hw_args = ["-c:v", encoder_name, *enc_params]

        flags = 0x08000000 if os.name == "nt" else 0

        if asset_path and asset_path.is_file():
            # Build template filtergraph using actual source video/image
            fg = build_template_filtergraph(
                template_id=template_id,
                target_width=TARGET_WIDTH,
                target_height=TARGET_HEIGHT,
                hook_text=hook_text,
            )
            cmd = [
                self.ffmpeg,
                "-y",
                "-nostdin",
                "-ss",
                str(scene.start_sec),
                "-t",
                str(dur),
                "-i",
                str(asset_path),
                "-filter_complex",
                fg,
                "-map",
                "[outv]",
                *hw_args,
                "-r",
                str(TARGET_FPS),
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(output_file),
            ]
        else:
            # Fallback aesthetic dark gradient card for scenes without assets
            color_expr = (
                f"color=c=0x0D1117:s={TARGET_WIDTH}x{TARGET_HEIGHT}:d={dur},"
                f"drawbox=y=0:height=180:color=0x161B22:t=fill"
            )
            cmd = [
                self.ffmpeg,
                "-y",
                "-nostdin",
                "-f",
                "lavfi",
                "-i",
                color_expr,
                *hw_args,
                "-r",
                str(TARGET_FPS),
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(output_file),
            ]

        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
        if res.returncode != 0 or not output_file.is_file():
            logger.error("Lỗi render cảnh %s: %s", scene.id, res.stderr[:300])
            raise RuntimeError(f"FFmpeg render cảnh {scene.id} thất bại: {res.stderr[:200]}")

        return output_file

    def render_project(
        self,
        project: AutoVideoProject,
        progress_cb: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Render complete project into final 9:16 vertical MP4 video."""
        proj_dir = self.work_dir / project.id
        proj_dir.mkdir(parents=True, exist_ok=True)
        final_mp4 = proj_dir / f"KAPPAK_AutoVideo_{project.id[:8]}.mp4"

        scenes = project.scenes
        if not scenes:
            raise ValueError("Dự án chưa có cảnh nào để dựng video.")

        total_steps = len(scenes) + 4
        current_step = 0

        # Step 1: Render individual video segments
        segment_files: list[Path] = []
        for i, scene in enumerate(scenes):
            current_step += 1
            if progress_cb:
                pct = round((current_step / total_steps) * 100, 1)
                progress_cb(pct, f"Dựng khung hình 9:16 cảnh {i + 1}/{len(scenes)}...")

            hook = scene.text if project.template_id == "caption_header" and i == 0 else ""
            seg_file = proj_dir / f"seg_{i:03d}_{scene.id}.mp4"
            self.render_scene_video(scene, project.template_id, seg_file, hook_text=hook)
            segment_files.append(seg_file)

        # Step 2: Concat video segments together
        current_step += 1
        if progress_cb:
            progress_cb(round((current_step / total_steps) * 100, 1), "Ghép nối các cảnh video...")

        concat_list_file = proj_dir / "concat_list.txt"
        concat_content = "".join([f"file '{p.resolve().as_posix()}'\n" for p in segment_files])
        concat_list_file.write_text(concat_content, encoding="utf-8")

        raw_concatenated_video = proj_dir / "raw_concat.mp4"
        flags = 0x08000000 if os.name == "nt" else 0
        cmd_concat = [
            self.ffmpeg,
            "-y",
            "-nostdin",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_file),
            "-c",
            "copy",
            str(raw_concatenated_video),
        ]
        res = subprocess.run(cmd_concat, capture_output=True, text=True, creationflags=flags)
        if res.returncode != 0:
            raise RuntimeError(f"Ghép video concat thất bại: {res.stderr[:200]}")

        # Step 3: Concat voice audios & mix BGM
        current_step += 1
        if progress_cb:
            progress_cb(
                round((current_step / total_steps) * 100, 1), "Hòa âm giọng đọc AI & nhạc nền..."
            )

        voice_files = [
            Path(s.voice_audio_path)
            for s in scenes
            if s.voice_audio_path and Path(s.voice_audio_path).is_file()
        ]
        master_audio_file = proj_dir / "master_audio.mp3"

        if voice_files:
            audio_concat_list = proj_dir / "audio_concat.txt"
            audio_content = "".join([f"file '{p.resolve().as_posix()}'\n" for p in voice_files])
            audio_concat_list.write_text(audio_content, encoding="utf-8")

            cmd_audio = [
                self.ffmpeg,
                "-y",
                "-nostdin",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(audio_concat_list),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(master_audio_file),
            ]
            subprocess.run(cmd_audio, capture_output=True, text=True, creationflags=flags)

        # Step 4: Burn subtitles and produce final video
        current_step += 1
        if progress_cb:
            progress_cb(
                round((current_step / total_steps) * 100, 1),
                "Nướng phụ đề động & xuất video 9:16...",
            )

        ass_file = proj_dir / "captions.ass"
        generate_ass_subtitles(scenes, ass_file)

        # Build final mux command
        sub_filter = f"ass='{ass_file.resolve().as_posix()}'"
        final_cmd = [
            self.ffmpeg,
            "-y",
            "-nostdin",
            "-i",
            str(raw_concatenated_video),
        ]

        if master_audio_file.is_file():
            final_cmd.extend(["-i", str(master_audio_file)])
            final_cmd.extend(["-vf", sub_filter])
            final_cmd.extend(["-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"])
            final_cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-shortest"])
        else:
            final_cmd.extend(["-vf", sub_filter])
            final_cmd.extend(["-c:v", "libx264", "-preset", "fast", "-an"])

        final_cmd.append(str(final_mp4))

        res = subprocess.run(final_cmd, capture_output=True, text=True, creationflags=flags)
        if res.returncode != 0 or not final_mp4.is_file():
            raise RuntimeError(f"Xuất video hoàn chỉnh thất bại: {res.stderr[:200]}")

        # Final step
        project.output_video_path = str(final_mp4)
        project.status = "COMPLETED"
        project.progress_pct = 100.0

        if progress_cb:
            progress_cb(100.0, "🎉 Xuất video ngắn 9:16 hoàn tất thành công!")

        # Send rich Discord announcement
        try:
            embed = {
                "title": f"🎉 XUẤT VIDEO TỰ ĐỘNG THÀNH CÔNG: {project.name}",
                "description": f"Video ngắn định dạng dọc 9:16 đã được render thành công với {len(scenes)} cảnh.",
                "color": 0x30D158,
                "fields": [
                    {"name": "Template", "value": project.template_id, "inline": True},
                    {"name": "Giọng đọc", "value": project.voice_id, "inline": True},
                    {
                        "name": "Tệp đầu ra",
                        "value": f"`{final_mp4.name}` ({round(final_mp4.stat().st_size / (1024 * 1024), 2)} MB)",
                        "inline": False,
                    },
                ],
                "footer": {"text": "KAPPAK Auto Video Generator"},
            }
            send_discord_message(embeds=[embed])
        except Exception:
            pass

        return final_mp4
