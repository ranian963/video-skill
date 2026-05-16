#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "ImageHash>=4.3.1",
#   "opencv-python-headless>=4.8.0",
#   "Pillow>=10.0.0",
#   "scenedetect>=0.6.5,<0.8",
# ]
# ///
"""Detect scenes, extract useful frames, and deduplicate near-identical images."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image
import imagehash
from scenedetect import detect
from scenedetect.detectors import AdaptiveDetector, ContentDetector


VISUAL_CUES = (
    "보시면",
    "여기",
    "화면",
    "슬라이드",
    "코드",
    "표",
    "그래프",
    "이미지",
    "데모",
    "예제",
    "look",
    "screen",
    "slide",
    "code",
    "diagram",
    "chart",
    "demo",
    "example",
)


@dataclass(frozen=True)
class FrameCandidate:
    timestamp: float
    reason: str
    weight: float
    scene_start: float | None = None
    scene_end: float | None = None
    transcript_text: str = ""


@dataclass(frozen=True)
class ExtractedFrame:
    timestamp: float
    path: str
    reason: str
    weight: float
    hash: str
    scene_start: float | None
    scene_end: float | None
    transcript_text: str
    size_bytes: int


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required for frame extraction.")


def ffprobe_value(video_path: Path, entries: str) -> str:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        entries,
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return result.stdout.strip()


def get_duration(video_path: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe duration failed")
    return float(result.stdout.strip())


def get_fps(video_path: Path) -> float:
    raw = ffprobe_value(video_path, "stream=r_frame_rate")
    if "/" in raw:
        numerator, denominator = raw.split("/", 1)
        return float(numerator) / max(float(denominator), 1.0)
    return float(raw or 30.0)


def scene_seconds(scene: tuple[Any, Any]) -> tuple[float, float]:
    return (float(scene[0].get_seconds()), float(scene[1].get_seconds()))


def detect_video_scenes(video_path: Path, threshold: float, min_scene_seconds: float) -> list[tuple[float, float]]:
    fps = get_fps(video_path)
    min_scene_len = max(1, int(fps * min_scene_seconds))
    detectors = (
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
        AdaptiveDetector(min_scene_len=min_scene_len),
    )
    found = []
    for detector in detectors:
        try:
            found.extend(scene_seconds(scene) for scene in detect(str(video_path), detector))
        except Exception:
            continue
    return merge_scenes(found, min_scene_seconds)


def merge_scenes(scenes: list[tuple[float, float]], min_scene_seconds: float) -> list[tuple[float, float]]:
    filtered = sorted({(round(start, 3), round(end, 3)) for start, end in scenes if end - start >= min_scene_seconds})
    merged: list[tuple[float, float]] = []
    for start, end in filtered:
        if merged and abs(start - merged[-1][0]) < 0.75 and abs(end - merged[-1][1]) < 0.75:
            previous = merged[-1]
            merged[-1] = (min(previous[0], start), max(previous[1], end))
        else:
            merged.append((start, end))
    return merged


def frame_budget(duration_seconds: float, per_minute: float, minimum: int, maximum: int) -> int:
    proportional = math.ceil((duration_seconds / 60) * per_minute)
    return max(minimum, min(maximum, proportional))


def scene_candidates(scenes: list[tuple[float, float]]) -> list[FrameCandidate]:
    return [
        FrameCandidate(
            timestamp=(start + end) / 2,
            reason="scene-midpoint",
            weight=2.0,
            scene_start=start,
            scene_end=end,
        )
        for start, end in scenes
    ]


def transcript_candidates(transcript_path: Path | None) -> list[FrameCandidate]:
    if transcript_path is None or not transcript_path.exists():
        return []
    payload = read_json(transcript_path)
    segments = payload.get("segments") or []
    candidates = []
    for segment in segments:
        text = str(segment.get("text") or "")
        lower = text.lower()
        cue_hits = sum(1 for cue in VISUAL_CUES if cue in lower or cue in text)
        capital_terms = re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", text)
        if cue_hits or len(set(capital_terms)) >= 2:
            start = float(segment.get("start") or 0.0)
            end = float(segment.get("end") or start + 1.0)
            candidates.append(
                FrameCandidate(
                    timestamp=max(start + 0.5, (start + end) / 2),
                    reason="transcript-visual-cue",
                    weight=4.0 + cue_hits + min(len(set(capital_terms)), 3) * 0.25,
                    scene_start=start,
                    scene_end=end,
                    transcript_text=text[:240],
                )
            )
    return candidates


def chapter_candidates(info_json: Path | None) -> list[FrameCandidate]:
    if info_json is None or not info_json.exists():
        return []
    info = read_json(info_json)
    chapters = info.get("chapters") or []
    return [
        FrameCandidate(
            timestamp=float(chapter.get("start_time") or 0.0) + 1.0,
            reason="chapter-start",
            weight=3.0,
            scene_start=chapter.get("start_time"),
            scene_end=chapter.get("end_time"),
            transcript_text=str(chapter.get("title") or "")[:240],
        )
        for chapter in chapters
    ]


def uniform_candidates(duration_seconds: float, count: int) -> list[FrameCandidate]:
    if duration_seconds <= 0 or count <= 0:
        return []
    return [
        FrameCandidate(
            timestamp=((index + 1) * duration_seconds) / (count + 1),
            reason="uniform-fallback",
            weight=1.0,
        )
        for index in range(count)
    ]


def dedupe_candidate_times(candidates: list[FrameCandidate], duration_seconds: float) -> list[FrameCandidate]:
    ordered = sorted(
        candidates,
        key=lambda candidate: (-candidate.weight, round(candidate.timestamp, 1), candidate.reason),
    )
    seen: set[int] = set()
    unique = []
    for candidate in ordered:
        timestamp = min(max(candidate.timestamp, 0.1), max(duration_seconds - 0.1, 0.1))
        bucket = int(timestamp * 2)
        if bucket in seen:
            continue
        seen.add(bucket)
        unique.append(
            FrameCandidate(
                timestamp=timestamp,
                reason=candidate.reason,
                weight=candidate.weight,
                scene_start=candidate.scene_start,
                scene_end=candidate.scene_end,
                transcript_text=candidate.transcript_text,
            )
        )
    return unique


def build_candidates(
    video_path: Path,
    transcript_path: Path | None,
    info_json: Path | None,
    threshold: float,
    min_scene_seconds: float,
    per_minute: float,
    min_frames: int,
    max_frames: int,
) -> tuple[list[FrameCandidate], list[tuple[float, float]], int, float]:
    duration = get_duration(video_path)
    scenes = detect_video_scenes(video_path, threshold, min_scene_seconds)
    budget = frame_budget(duration, per_minute, min_frames, max_frames)
    raw_candidates = [
        *transcript_candidates(transcript_path),
        *chapter_candidates(info_json),
        *scene_candidates(scenes),
        *uniform_candidates(duration, budget),
    ]
    candidates = dedupe_candidate_times(raw_candidates, duration)
    return candidates, scenes, budget, duration


def extract_frame(video_path: Path, timestamp: float, output_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    result = run_command(command)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(result.stderr.strip() or f"Frame extraction failed at {timestamp:.3f}s")


def perceptual_hash(path: Path) -> imagehash.ImageHash:
    with Image.open(path) as image:
        return imagehash.phash(image)


def extract_useful_frames(
    video_path: Path,
    output_dir: Path,
    candidates: list[FrameCandidate],
    budget: int,
    hamming_threshold: int,
) -> list[ExtractedFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected: list[ExtractedFrame] = []
    hashes: list[imagehash.ImageHash] = []
    for candidate in candidates:
        if len(selected) >= budget:
            break
        frame_path = output_dir / f"frame_{len(selected) + 1:03d}_{candidate.timestamp:09.3f}.jpg"
        try:
            extract_frame(video_path, candidate.timestamp, frame_path)
            current_hash = perceptual_hash(frame_path)
        except Exception:
            if frame_path.exists():
                frame_path.unlink()
            continue
        if any(current_hash - previous <= hamming_threshold for previous in hashes):
            frame_path.unlink(missing_ok=True)
            continue
        hashes.append(current_hash)
        selected.append(
            ExtractedFrame(
                timestamp=candidate.timestamp,
                path=str(frame_path),
                reason=candidate.reason,
                weight=candidate.weight,
                hash=str(current_hash),
                scene_start=candidate.scene_start,
                scene_end=candidate.scene_end,
                transcript_text=candidate.transcript_text,
                size_bytes=frame_path.stat().st_size,
            )
        )
    return sorted(selected, key=lambda frame: frame.timestamp)


def create_frames_manifest(
    video_path: Path,
    transcript_path: Path | None,
    info_json: Path | None,
    output_dir: Path,
    threshold: float,
    min_scene_seconds: float,
    per_minute: float,
    min_frames: int,
    max_frames: int,
    hamming_threshold: int,
) -> Path:
    require_ffmpeg()
    candidates, scenes, budget, duration = build_candidates(
        video_path,
        transcript_path,
        info_json,
        threshold,
        min_scene_seconds,
        per_minute,
        min_frames,
        max_frames,
    )
    frames_dir = output_dir / "frames"
    frames = extract_useful_frames(video_path, frames_dir, candidates, budget, hamming_threshold)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video": str(video_path),
        "duration_seconds": duration,
        "scene_count": len(scenes),
        "candidate_count": len(candidates),
        "frame_budget": budget,
        "frames": [asdict(frame) for frame in frames],
        "settings": {
            "content_threshold": threshold,
            "min_scene_seconds": min_scene_seconds,
            "per_minute": per_minute,
            "min_frames": min_frames,
            "max_frames": max_frames,
            "hamming_threshold": hamming_threshold,
        },
    }
    manifest_path = output_dir / "frames_manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect scenes and extract representative frames.")
    parser.add_argument("--video", required=True, help="Input video path")
    parser.add_argument("--output-dir", required=True, help="Output working directory")
    parser.add_argument("--transcript", default=None, help="Optional transcript.json path")
    parser.add_argument("--info-json", default=None, help="Optional yt-dlp info JSON path")
    parser.add_argument("--threshold", type=float, default=27.0, help="ContentDetector threshold")
    parser.add_argument("--min-scene-seconds", type=float, default=2.0, help="Minimum scene length")
    parser.add_argument("--per-minute", type=float, default=2.0, help="Frame budget per minute")
    parser.add_argument("--min-frames", type=int, default=12, help="Minimum frame budget")
    parser.add_argument("--max-frames", type=int, default=50, help="Maximum frame budget")
    parser.add_argument("--hamming-threshold", type=int, default=6, help="pHash duplicate threshold")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = create_frames_manifest(
            video_path=Path(args.video),
            transcript_path=Path(args.transcript) if args.transcript else None,
            info_json=Path(args.info_json) if args.info_json else None,
            output_dir=Path(args.output_dir),
            threshold=args.threshold,
            min_scene_seconds=args.min_scene_seconds,
            per_minute=args.per_minute,
            min_frames=args.min_frames,
            max_frames=args.max_frames,
            hamming_threshold=args.hamming_threshold,
        )
    except Exception as error:
        print(f"Scene detection failed: {error}", file=sys.stderr)
        return 1
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
