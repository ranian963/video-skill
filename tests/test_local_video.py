from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "youtube-summarizer" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def create_sample_video(path: Path) -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required for local video tests")
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=160x90:rate=10",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:duration=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_create_local_video_manifest_extracts_audio(tmp_path: Path) -> None:
    from local_video import create_local_video_manifest

    source = tmp_path / "demo video.mp4"
    output_root = tmp_path / "out"
    create_sample_video(source)

    result = create_local_video_manifest(source, output_root)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.video_path == source.resolve()
    assert result.audio_path is not None
    assert result.audio_path.exists()
    assert manifest["source_type"] == "local_file"
    assert manifest["source_path"] == str(source.resolve())
    assert manifest["metadata"]["title"] == "demo video"
    assert manifest["metadata"]["width"] == 160
    assert manifest["metadata"]["height"] == 90
    assert manifest["files"]["comments"] is None
    assert manifest["subtitle_candidates"] == []
