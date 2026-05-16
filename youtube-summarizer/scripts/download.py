#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "yt-dlp>=2025.1.1",
# ]
# ///
"""Download YouTube metadata, comments, subtitles, video, and audio."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL


SUBTITLE_EXTENSIONS = {".vtt", ".srt", ".json3", ".srv1", ".srv2", ".srv3", ".ttml"}


@dataclass(frozen=True)
class DownloadResult:
    work_dir: Path
    info_json: Path | None
    video_path: Path | None
    audio_path: Path | None
    subtitle_candidates: tuple[dict[str, Any], ...]
    comments_path: Path | None
    manifest_path: Path


def sanitize_filename(value: str, fallback: str = "youtube-video") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:90] or fallback).strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes().decode("utf-8", errors="replace"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(command: list[str]) -> None:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{detail}")


def get_preflight_info(url: str) -> dict[str, Any]:
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "noplaylist": True,
    }
    with YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


def build_work_dir(output_root: Path, info: dict[str, Any]) -> Path:
    title = sanitize_filename(str(info.get("title") or "youtube-video"))
    video_id = str(info.get("id") or "unknown")
    work_dir = output_root / f"{title}-{video_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def ydl_options(work_dir: Path, languages: list[str], max_height: int, max_comments: int) -> dict[str, Any]:
    subtitle_langs = ",".join(languages)
    return {
        "format": (
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(work_dir / "source.%(ext)s"),
        "writeinfojson": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": languages,
        "subtitlesformat": "vtt/best",
        "getcomments": True,
        "writecomments": True,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "extractor_args": {
            "youtube": {
                "comment_sort": ["top"],
                "max_comments": [str(max_comments)],
                "skip": [] if max_comments > 0 else ["comments"],
                "player_skip": ["configs"],
            }
        },
        "postprocessors": [
            {"key": "FFmpegMetadata"},
        ],
        "postprocessor_args": {
            "ffmpeg": ["-movflags", "use_metadata_tags"],
        },
        "concurrent_fragment_downloads": 4,
        "retries": 3,
        "fragment_retries": 3,
        "ignoreerrors": False,
        "cachedir": False,
        "subtitleslangs_cli": subtitle_langs,
    }


def locate_info_json(work_dir: Path) -> Path | None:
    candidates = sorted(work_dir.glob("*.info.json"))
    return candidates[0] if candidates else None


def locate_video(work_dir: Path) -> Path | None:
    candidates = [
        path
        for path in sorted(work_dir.glob("source.*"))
        if path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
    ]
    return candidates[0] if candidates else None


def subtitle_kind_from_info(info: dict[str, Any], language: str) -> str:
    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    if language in subtitles:
        return "manual"
    if language in automatic:
        return "automatic"
    return "unknown"


def parse_subtitle_path(path: Path, info: dict[str, Any]) -> dict[str, Any]:
    parts = path.name.split(".")
    language = parts[-2] if len(parts) >= 3 else "unknown"
    return {
        "path": str(path),
        "language": language,
        "kind": subtitle_kind_from_info(info, language),
        "format": path.suffix.lstrip("."),
        "size_bytes": path.stat().st_size,
    }


def locate_subtitles(work_dir: Path, info: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    paths = [
        path
        for path in sorted(work_dir.glob("source.*"))
        if path.suffix.lower() in SUBTITLE_EXTENSIONS
    ]
    return tuple(parse_subtitle_path(path, info) for path in paths)


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to extract audio.")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]
    run_command(command)
    return audio_path


def normalized_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "author": comment.get("author"),
        "text": comment.get("text"),
        "like_count": comment.get("like_count"),
        "timestamp": comment.get("timestamp"),
        "parent": comment.get("parent"),
    }


def write_comments(info: dict[str, Any], work_dir: Path, max_comments: int) -> Path | None:
    comments = info.get("comments") or []
    if not comments:
        return None
    ranked = sorted(
        comments[:max_comments],
        key=lambda item: int(item.get("like_count") or 0),
        reverse=True,
    )
    payload = {
        "count": len(ranked),
        "comments": [normalized_comment(comment) for comment in ranked],
    }
    comments_path = work_dir / "comments.json"
    write_json(comments_path, payload)
    return comments_path


def metadata_receipt(info: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "id",
        "title",
        "channel",
        "channel_id",
        "uploader",
        "upload_date",
        "duration",
        "view_count",
        "like_count",
        "tags",
        "description",
        "webpage_url",
    ]
    return {key: info.get(key) for key in keys if key in info}


def build_manifest(
    url: str,
    work_dir: Path,
    info_json: Path | None,
    info: dict[str, Any],
    video_path: Path | None,
    audio_path: Path | None,
    subtitle_candidates: tuple[dict[str, Any], ...],
    comments_path: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "work_dir": str(work_dir),
        "metadata": metadata_receipt(info),
        "files": {
            "info_json": str(info_json) if info_json else None,
            "video": str(video_path) if video_path else None,
            "audio": str(audio_path) if audio_path else None,
            "comments": str(comments_path) if comments_path else None,
        },
        "subtitle_candidates": list(subtitle_candidates),
    }


def download_video(
    url: str,
    output_root: Path,
    languages: list[str],
    max_height: int,
    max_comments: int,
) -> DownloadResult:
    preflight = get_preflight_info(url)
    work_dir = build_work_dir(output_root, preflight)
    options = ydl_options(work_dir, languages, max_height, max_comments)

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    info_json = locate_info_json(work_dir)
    persisted_info = read_json(info_json) if info_json else info
    video_path = locate_video(work_dir)
    audio_path = extract_audio(video_path, work_dir / "audio.wav") if video_path else None
    subtitles = locate_subtitles(work_dir, persisted_info)
    comments_path = write_comments(persisted_info, work_dir, max_comments)
    manifest = build_manifest(
        url,
        work_dir,
        info_json,
        persisted_info,
        video_path,
        audio_path,
        subtitles,
        comments_path,
    )
    manifest_path = work_dir / "download_manifest.json"
    write_json(manifest_path, manifest)
    return DownloadResult(
        work_dir=work_dir,
        info_json=info_json,
        video_path=video_path,
        audio_path=audio_path,
        subtitle_candidates=subtitles,
        comments_path=comments_path,
        manifest_path=manifest_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download YouTube assets for summarization.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--output-root", default="downloads", help="Output root directory")
    parser.add_argument("--languages", default="ko,en", help="Comma-separated subtitle languages")
    parser.add_argument("--max-height", type=int, default=480, help="Maximum video height")
    parser.add_argument("--max-comments", type=int, default=100, help="Maximum comments to retain")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    languages = [item.strip() for item in args.languages.split(",") if item.strip()]
    try:
        result = download_video(
            url=args.url,
            output_root=Path(args.output_root),
            languages=languages or ["ko", "en"],
            max_height=args.max_height,
            max_comments=args.max_comments,
        )
    except Exception as error:
        print(f"Download failed: {error}", file=sys.stderr)
        return 1

    print(result.manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
