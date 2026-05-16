#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "elevenlabs>=2.0.0",
#   "python-dotenv>=1.0.1",
#   "webvtt-py>=0.5.1",
# ]
# ///
"""Choose subtitles first, then fall back to ElevenLabs or local faster-whisper."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import webvtt
from dotenv import load_dotenv


@dataclass(frozen=True)
class TranscriptResult:
    source: str
    language: str | None
    transcript_json: Path
    transcript_txt: Path
    transcript_vtt: Path
    segment_count: int


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def collapse_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", without_tags).strip()


def parse_timestamp(value: str) -> float:
    match = re.match(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})", value)
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int(match.group(4))
    return (hours * 3600) + (minutes * 60) + seconds + (millis / 1000)


def format_timestamp(seconds: float) -> str:
    safe = max(0.0, seconds)
    hours = int(safe // 3600)
    minutes = int((safe % 3600) // 60)
    secs = safe % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def subtitle_score(candidate: dict[str, Any], preferred_languages: list[str]) -> tuple[int, int, int]:
    language = str(candidate.get("language") or "")
    language_rank = preferred_languages.index(language) if language in preferred_languages else 99
    kind_rank = 0 if candidate.get("kind") == "manual" else 1
    size_rank = -int(candidate.get("size_bytes") or 0)
    return (kind_rank, language_rank, size_rank)


def choose_subtitle(
    candidates: list[dict[str, Any]],
    preferred_languages: list[str],
) -> dict[str, Any] | None:
    available = [item for item in candidates if Path(str(item.get("path"))).exists()]
    if not available:
        return None
    return sorted(available, key=lambda item: subtitle_score(item, preferred_languages))[0]


def parse_vtt(path: Path) -> list[dict[str, Any]]:
    parsed = webvtt.read(str(path))
    segments = [
        {
            "start": parse_timestamp(caption.start),
            "end": parse_timestamp(caption.end),
            "text": collapse_text(caption.text),
        }
        for caption in parsed
        if collapse_text(caption.text)
    ]
    return merge_duplicate_segments(segments)


def parse_json3(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    events = payload.get("events") or []
    segments = []
    for event in events:
        start = float(event.get("tStartMs") or 0) / 1000
        duration = float(event.get("dDurationMs") or 0) / 1000
        text = collapse_text("".join(seg.get("utf8", "") for seg in event.get("segs") or []))
        if text:
            segments.append({"start": start, "end": start + duration, "text": text})
    return merge_duplicate_segments(segments)


def parse_plain_subtitle(path: Path) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\s*\n", content)
    segments = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timestamp = next((line for line in lines if "-->" in line), "")
        if not timestamp:
            continue
        start_raw, end_raw = [part.strip().split()[0] for part in timestamp.split("-->", 1)]
        text = collapse_text(" ".join(line for line in lines if "-->" not in line and not line.isdigit()))
        if text:
            segments.append(
                {
                    "start": parse_timestamp(start_raw),
                    "end": parse_timestamp(end_raw),
                    "text": text,
                }
            )
    return merge_duplicate_segments(segments)


def merge_duplicate_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for segment in segments:
        if merged and segment["text"] == merged[-1]["text"]:
            previous = merged[-1]
            merged[-1] = {**previous, "end": max(previous["end"], segment["end"])}
        else:
            merged.append(segment)
    return merged


def parse_subtitle(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".vtt":
        return parse_vtt(path)
    if suffix == ".json3":
        return parse_json3(path)
    return parse_plain_subtitle(path)


def segments_text(segments: list[dict[str, Any]]) -> str:
    return "\n".join(collapse_text(str(segment.get("text") or "")) for segment in segments).strip()


def load_local_env(skill_dir: Path) -> None:
    for env_path in (Path.cwd() / ".env", skill_dir / ".env"):
        if env_path.exists():
            load_dotenv(env_path)


def to_plain_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, list):
        return [to_plain_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain_dict(item) for key, item in value.items()}
    return value


def join_token(existing: str, token: str) -> str:
    if not existing:
        return token.strip()
    if re.match(r"^[,.;:!?%)]", token):
        return f"{existing}{token.strip()}"
    if re.match(r"^[가-힣]+$", token) and re.search(r"[가-힣]$", existing):
        return f"{existing} {token.strip()}"
    return f"{existing} {token.strip()}"


def words_to_segments(words: list[dict[str, Any]], max_seconds: float = 18.0) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for word in words:
        text = str(word.get("text") or "").strip()
        start = word.get("start")
        end = word.get("end")
        if not text or start is None or end is None:
            continue
        speaker = word.get("speaker_id")
        should_split = (
            current is not None
            and (
                speaker != current.get("speaker")
                or float(start) - float(current["end"]) > 1.5
                or float(end) - float(current["start"]) > max_seconds
                or str(current["text"]).endswith((".", "?", "!", "다.", "요."))
            )
        )
        if current is None or should_split:
            if current is not None:
                segments.append(current)
            current = {
                "start": float(start),
                "end": float(end),
                "text": text,
                "speaker": speaker,
            }
        else:
            current = {
                **current,
                "end": float(end),
                "text": join_token(str(current["text"]), text),
            }
    if current is not None:
        segments.append(current)
    return segments


def transcribe_with_elevenlabs(
    audio_path: Path,
    language: str | None,
    keyterms: list[str],
    skill_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    load_local_env(skill_dir)
    if not os.environ.get("ELEVENLABS_API_KEY"):
        raise RuntimeError("Set ELEVENLABS_API_KEY or rerun with --local for local STT.")

    from elevenlabs import ElevenLabs

    client = ElevenLabs()
    with audio_path.open("rb") as audio:
        result = client.speech_to_text.convert(
            file=audio,
            model_id="scribe_v2",
            language_code=language,
            diarize=True,
            tag_audio_events=True,
            keyterms=keyterms or None,
        )
    payload = to_plain_dict(result)
    words = payload.get("words") or []
    segments = words_to_segments(words)
    if not segments and payload.get("text"):
        segments = [{"start": 0.0, "end": 0.0, "text": collapse_text(payload["text"])}]
    return segments, payload


def transcribe_with_faster_whisper(
    audio_path: Path,
    language: str | None,
    model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError(
            "faster-whisper is not installed. Run with: "
            "uv run --with faster-whisper scripts/transcribe.py --local ..."
        ) from error

    whisper = WhisperModel(model, device="auto", compute_type="auto")
    lang = None if language in {None, "auto"} else language
    segments_iter, info = whisper.transcribe(str(audio_path), language=lang, vad_filter=True)
    segments = [
        {
            "start": float(segment.start),
            "end": float(segment.end),
            "text": collapse_text(segment.text),
        }
        for segment in segments_iter
        if collapse_text(segment.text)
    ]
    payload = {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "model": model,
    }
    return segments, payload


def write_outputs(
    output_dir: Path,
    source: str,
    language: str | None,
    segments: list[dict[str, Any]],
    raw_payload: dict[str, Any] | None = None,
) -> TranscriptResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_json = output_dir / "transcript.json"
    transcript_txt = output_dir / "transcript.txt"
    transcript_vtt = output_dir / "transcript.vtt"
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "language": language,
        "segments": segments,
        "text": segments_text(segments),
    }
    if raw_payload:
        payload = {**payload, "raw": raw_payload}
    write_json(transcript_json, payload)
    transcript_txt.write_text(payload["text"] + "\n", encoding="utf-8")
    write_vtt(segments, transcript_vtt)
    return TranscriptResult(
        source=source,
        language=language,
        transcript_json=transcript_json,
        transcript_txt=transcript_txt,
        transcript_vtt=transcript_vtt,
        segment_count=len(segments),
    )


def write_vtt(segments: list[dict[str, Any]], path: Path) -> None:
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.extend(
            [
                f"{format_timestamp(float(segment['start']))} --> {format_timestamp(float(segment['end']))}",
                str(segment["text"]),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def read_keyterms(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    terms = [line.strip("- ").strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [term for term in terms if term and not term.startswith("#")][:1000]


def transcript_from_download_manifest(
    manifest_path: Path,
    output_dir: Path | None,
    preferred_languages: list[str],
    force_stt: bool,
    local: bool,
    language: str | None,
    model: str,
    keyterms_path: Path | None,
    min_subtitle_chars: int,
    skill_dir: Path,
) -> TranscriptResult:
    manifest = read_json(manifest_path)
    work_dir = Path(str(manifest["work_dir"]))
    destination = output_dir or work_dir
    subtitle = choose_subtitle(manifest.get("subtitle_candidates") or [], preferred_languages)
    audio = manifest.get("files", {}).get("audio")
    if subtitle and not force_stt:
        subtitle_path = Path(str(subtitle["path"]))
        segments = parse_subtitle(subtitle_path)
        if len(segments_text(segments)) >= min_subtitle_chars or not audio:
            return write_outputs(
                destination,
                source=f"subtitle:{subtitle.get('kind', 'unknown')}",
                language=str(subtitle.get("language") or language or ""),
                segments=segments,
            )

    if not audio:
        raise RuntimeError("No usable subtitle and no audio file found for STT fallback.")
    audio_path = Path(str(audio))
    keyterms = read_keyterms(keyterms_path)
    if local:
        segments, raw = transcribe_with_faster_whisper(audio_path, language, model)
        return write_outputs(destination, "stt:faster-whisper", language, segments, raw)
    segments, raw = transcribe_with_elevenlabs(audio_path, language, keyterms, skill_dir)
    return write_outputs(destination, "stt:elevenlabs-scribe-v2", language, segments, raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create transcript assets for a downloaded video.")
    parser.add_argument("--download-manifest", required=True, help="Path to download_manifest.json")
    parser.add_argument("--output-dir", default=None, help="Directory for transcript outputs")
    parser.add_argument("--preferred-languages", default="ko,en", help="Comma-separated subtitle language order")
    parser.add_argument("--language", default="ko", help="STT language code or auto")
    parser.add_argument("--local", action="store_true", help="Use faster-whisper instead of ElevenLabs")
    parser.add_argument("--force-stt", action="store_true", help="Ignore subtitles and run STT")
    parser.add_argument("--model", default="large-v3", help="faster-whisper model for --local")
    parser.add_argument("--keyterms", default=None, help="Optional newline-delimited keyterms file")
    parser.add_argument("--min-subtitle-chars", type=int, default=120, help="Minimum subtitle text length")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preferred = [item.strip() for item in args.preferred_languages.split(",") if item.strip()]
    language = None if args.language == "auto" else args.language
    skill_dir = Path(__file__).resolve().parents[1]
    try:
        result = transcript_from_download_manifest(
            manifest_path=Path(args.download_manifest),
            output_dir=Path(args.output_dir) if args.output_dir else None,
            preferred_languages=preferred or ["ko", "en"],
            force_stt=args.force_stt,
            local=args.local,
            language=language,
            model=args.model,
            keyterms_path=Path(args.keyterms) if args.keyterms else None,
            min_subtitle_chars=args.min_subtitle_chars,
            skill_dir=skill_dir,
        )
    except Exception as error:
        print(f"Transcription failed: {error}", file=sys.stderr)
        return 1
    print(result.transcript_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
