#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "ImageHash>=4.3.1",
#   "opencv-python-headless>=4.8.0",
#   "Pillow>=10.0.0",
#   "elevenlabs>=2.0.0",
#   "python-dotenv>=1.0.1",
#   "scenedetect>=0.6.5,<0.8",
#   "webvtt-py>=0.5.1",
#   "yt-dlp>=2025.1.1",
# ]
# ///
"""Prepare a YouTube video work folder and write a compact manifest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from download import download_video
from scene_detect import create_frames_manifest
from transcribe import transcript_from_download_manifest


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def existing_context_files(skill_dir: Path) -> list[str]:
    paths = [
        skill_dir / "context" / "company.md",
        skill_dir / "context" / "projects.md",
        skill_dir / "context" / "tech_stack.md",
        skill_dir / "context" / "competitors.md",
        skill_dir / "context" / "interests.md",
    ]
    return [str(path) for path in paths if path.exists()]


def existing_prompt_files(skill_dir: Path) -> dict[str, str]:
    paths = {
        "relevance": skill_dir / "prompts" / "relevance_check.md",
        "generic_summary": skill_dir / "prompts" / "generic_summary.md",
        "contextual_summary": skill_dir / "prompts" / "contextual_summary.md",
    }
    return {key: str(path) for key, path in paths.items() if path.exists()}


def create_final_manifest(
    skill_dir: Path,
    url: str,
    download_manifest_path: Path,
    transcript_json: Path,
    frames_manifest_path: Path,
) -> Path:
    download_manifest = read_json(download_manifest_path)
    transcript = read_json(transcript_json)
    frames_manifest = read_json(frames_manifest_path)
    work_dir = Path(str(download_manifest["work_dir"]))
    final_manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "work_dir": str(work_dir),
        "metadata": download_manifest.get("metadata") or {},
        "files": {
            **(download_manifest.get("files") or {}),
            "download_manifest": str(download_manifest_path),
            "transcript_json": str(transcript_json),
            "transcript_txt": str(transcript_json.with_suffix(".txt")),
            "transcript_vtt": str(transcript_json.with_suffix(".vtt")),
            "frames_manifest": str(frames_manifest_path),
        },
        "transcript": {
            "source": transcript.get("source"),
            "language": transcript.get("language"),
            "segment_count": len(transcript.get("segments") or []),
            "text_path": str(transcript_json.with_suffix(".txt")),
        },
        "frames": {
            "count": len(frames_manifest.get("frames") or []),
            "budget": frames_manifest.get("frame_budget"),
            "manifest_path": str(frames_manifest_path),
            "items": frames_manifest.get("frames") or [],
        },
        "context_files": existing_context_files(skill_dir),
        "prompt_files": existing_prompt_files(skill_dir),
        "next_steps": [
            "Read this manifest first; do not load full transcript or all frames into context.",
            "Run relevance scoring with prompts/relevance_check.md and context/*.md.",
            "Open only useful frame files for scene-level visual analysis.",
            "Write the final Korean Markdown summary to the requested output directory.",
        ],
    }
    manifest_path = work_dir / "manifest.json"
    write_json(manifest_path, final_manifest)
    return manifest_path


def prepare_video(args: argparse.Namespace, skill_dir: Path) -> Path:
    languages = [item.strip() for item in args.languages.split(",") if item.strip()]
    download_result = download_video(
        url=args.url,
        output_root=Path(args.output_root),
        languages=languages or ["ko", "en"],
        max_height=args.max_height,
        max_comments=args.max_comments,
    )
    if download_result.video_path is None:
        raise RuntimeError("Video download did not produce a video file.")
    transcript_result = transcript_from_download_manifest(
        manifest_path=download_result.manifest_path,
        output_dir=download_result.work_dir,
        preferred_languages=languages or ["ko", "en"],
        force_stt=args.force_stt,
        local=args.local,
        language=None if args.language == "auto" else args.language,
        model=args.local_model,
        keyterms_path=Path(args.keyterms) if args.keyterms else None,
        min_subtitle_chars=args.min_subtitle_chars,
        skill_dir=skill_dir,
    )
    frames_manifest = create_frames_manifest(
        video_path=download_result.video_path,
        transcript_path=transcript_result.transcript_json,
        info_json=download_result.info_json,
        output_dir=download_result.work_dir,
        threshold=args.scene_threshold,
        min_scene_seconds=args.min_scene_seconds,
        per_minute=args.frames_per_minute,
        min_frames=args.min_frames,
        max_frames=args.max_frames,
        hamming_threshold=args.hamming_threshold,
    )
    return create_final_manifest(
        skill_dir=skill_dir,
        url=args.url,
        download_manifest_path=download_result.manifest_path,
        transcript_json=transcript_result.transcript_json,
        frames_manifest_path=frames_manifest,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare YouTube summarization assets.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--output-root", default="downloads", help="Output root directory")
    parser.add_argument("--languages", default="ko,en", help="Subtitle language preference")
    parser.add_argument("--language", default="ko", help="STT language code or auto")
    parser.add_argument("--max-height", type=int, default=480, help="Maximum downloaded video height")
    parser.add_argument("--max-comments", type=int, default=100, help="Maximum comments to retain")
    parser.add_argument("--local", action="store_true", help="Use faster-whisper local STT")
    parser.add_argument("--force-stt", action="store_true", help="Ignore subtitles and run STT")
    parser.add_argument("--local-model", default="large-v3", help="faster-whisper model")
    parser.add_argument("--keyterms", default=None, help="Optional keyterms file for Scribe v2")
    parser.add_argument("--min-subtitle-chars", type=int, default=120)
    parser.add_argument("--scene-threshold", type=float, default=27.0)
    parser.add_argument("--min-scene-seconds", type=float, default=2.0)
    parser.add_argument("--frames-per-minute", type=float, default=2.0)
    parser.add_argument("--min-frames", type=int, default=12)
    parser.add_argument("--max-frames", type=int, default=50)
    parser.add_argument("--hamming-threshold", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skill_dir = Path(__file__).resolve().parents[1]
    try:
        manifest_path = prepare_video(args, skill_dir)
    except Exception as error:
        print(f"Prepare failed: {error}", file=sys.stderr)
        return 1
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
