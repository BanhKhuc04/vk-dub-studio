import sys
import time
from pathlib import Path

# Add src to sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from vkdub.web.server import probe_file, start_pipeline, state


def test_pipeline_execution():
    video_file = repo_root / "docs" / "evidence" / "media" / "sample_vertical_9_16.mp4"
    assert video_file.is_file(), f"Video file not found: {video_file}"

    state.project.video_path = video_file
    state.video_metadata = probe_file(video_file)
    state.project.video_duration_ms = int(state.video_metadata["duration"] * 1000)

    res = start_pipeline()
    assert res["status"] == "started"

    # Wait for completion
    for _ in range(40):
        time.sleep(0.5)
        if not (state.runner_thread and state.runner_thread.is_alive()):
            break

    print(f"Finished. Overall: {state.overall_pct}%, Subtitles: {len(state.subtitles)}")
    assert state.overall_pct == 100
    assert len(state.subtitles) > 0

if __name__ == "__main__":
    test_pipeline_execution()
