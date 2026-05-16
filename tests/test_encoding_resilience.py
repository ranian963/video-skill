from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "youtube-summarizer" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def test_download_read_json_replaces_invalid_utf8(tmp_path: Path) -> None:
    from download import read_json

    path = tmp_path / "source.info.json"
    path.write_bytes(b'{"title": "bad ' + bytes([0xFF]) + b' metadata"}')

    assert read_json(path)["title"] == "bad \ufffd metadata"


def test_prepare_read_json_replaces_invalid_utf8(tmp_path: Path) -> None:
    from prepare import read_json

    path = tmp_path / "manifest.json"
    path.write_bytes(b'{"title": "bad ' + bytes([0xFF]) + b' metadata"}')

    assert read_json(path)["title"] == "bad \ufffd metadata"


def test_scene_detect_run_command_uses_replacement_decoding(monkeypatch) -> None:
    import scene_detect

    captured_kwargs = {}

    def fake_run(command, **kwargs):
        captured_kwargs.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(scene_detect.subprocess, "run", fake_run)

    scene_detect.run_command(["ffmpeg", "-version"])

    assert captured_kwargs["encoding"] == "utf-8"
    assert captured_kwargs["errors"] == "replace"
