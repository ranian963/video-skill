#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Prepare local video files for the summarization pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalVideoResult:
    work_dir: Path
    info_json: None
    video_path: Path
    audio_path: Path | None
    subtitle_candidates: tuple[dict[str, Any], ...]
    comments_path: None
    manifest_path: Path


def sanitize_filename(value: str, fallback: str = "local-video") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:90] or fallback).strip()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required for local video files.")


def source_digest(source_path: Path) -> str:
    stat = source_path.stat()
    payload = f"{source_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:10]


def build_work_dir(source_path: Path, output_root: Path) -> Path:
    safe_title = sanitize_filename(source_path.stem)
    work_dir = output_root / f"{safe_title}-{source_digest(source_path)}"
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def probe_video(source_path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"ffprobe failed for {source_path}: {detail}")
    payload = json.loads(result.stdout)
    format_info = payload.get("format") or {}
    streams = payload.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    duration = format_info.get("duration") or video_stream.get("duration") or audio_stream.get("duration")
    return {
        "title": source_path.stem,
        "source_type": "local_file",
        "filename": source_path.name,
        "source_path": str(source_path.resolve()),
        "duration": float(duration) if duration is not None else None,
        "size_bytes": int(format_info.get("size") or source_path.stat().st_size),
        "format_name": format_info.get("format_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "avg_frame_rate": video_stream.get("avg_frame_rate"),
    }


def extract_audio(source_path: Path, audio_path: Path) -> Path:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"ffmpeg audio extraction failed for {source_path}: {detail}")
    return audio_path


def create_local_download_manifest(source_path: Path, work_dir: Path, metadata: dict[str, Any], audio_path: Path) -> Path:
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_type": "local_file",
        "url": None,
        "source_path": str(source_path.resolve()),
        "work_dir": str(work_dir),
        "metadata": metadata,
        "files": {
            "info_json": None,
            "video": str(source_path.resolve()),
            "audio": str(audio_path),
            "comments": None,
        },
        "subtitle_candidates": [],
    }
    manifest_path = work_dir / "download_manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path


def create_local_video_manifest(source: Path, output_root: Path) -> LocalVideoResult:
    require_ffmpeg()
    source_path = source.expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Local video file not found: {source}")
    if not source_path.is_file():
        raise ValueError(f"Local video source must be a file: {source}")

    work_dir = build_work_dir(source_path, output_root)
    metadata = probe_video(source_path)
    audio_path = extract_audio(source_path, work_dir / "audio.wav")
    manifest_path = create_local_download_manifest(source_path, work_dir, metadata, audio_path)
    return LocalVideoResult(
        work_dir=work_dir,
        info_json=None,
        video_path=source_path,
        audio_path=audio_path,
        subtitle_candidates=(),
        comments_path=None,
        manifest_path=manifest_path,
    )
