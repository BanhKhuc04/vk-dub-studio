import json

import pytest

from vkdub.media.ffprobe import parse_metadata


def payload(**overrides):
    video = {
        "codec_type": "video",
        "codec_name": "h264",
        "width": 1920,
        "height": 1080,
        "avg_frame_rate": "30000/1001",
    }
    video.update(overrides)
    return json.dumps({"streams": [video], "format": {"duration": "12.5", "size": "10000"}})


def test_video_without_audio_and_fractional_fps():
    metadata = parse_metadata(payload())
    assert metadata.duration == 12.5
    assert (metadata.width, metadata.height) == (1920, 1080)
    assert metadata.fps == pytest.approx(29.97003)
    assert metadata.audio_codec is None


def test_unknown_fps_falls_back():
    assert parse_metadata(payload(avg_frame_rate="0/0", r_frame_rate="25/1")).fps == 25


@pytest.mark.parametrize(
    "raw", ["invalid", "null", "{}", '{"streams":[]}', payload(width=0), payload(height="bad")]
)
def test_malformed_or_nonvideo_metadata(raw):
    with pytest.raises(ValueError):
        parse_metadata(raw)


def test_audio_and_cover_art():
    data = json.loads(payload())
    data["streams"].insert(0, {"codec_type": "video", "disposition": {"attached_pic": 1}})
    data["streams"].append({"codec_type": "audio", "codec_name": "aac"})
    assert parse_metadata(json.dumps(data)).audio_codec == "aac"
