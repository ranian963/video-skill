---
name: youtube-summarizer
description: "Prepare and summarize one YouTube video with transcript fallback, metadata, comments, visual frame analysis, and optional Hancom company-context interpretation. Use when the user provides a YouTube URL and asks to summarize, analyze, extract insights, create Korean notes, inspect visual content, or connect the video to Hancom projects, RAG, agents, document AI, evaluation, or enterprise AI."
---

# YouTube Summarizer

## Overview

Use this skill to turn one YouTube URL into a Korean Markdown summary that combines metadata, comments, transcript/STT, representative frames, and optional Hancom context.

Keep heavy data on disk. Read `manifest.json` first, then open only the transcript excerpts and frame images needed for the summary.

## Quick Start

From the skill directory:

```bash
bash scripts/install_deps.sh
uv run scripts/prepare.py "YOUTUBE_URL"
```

For private/internal videos, force local STT:

```bash
uv run --with faster-whisper scripts/prepare.py "YOUTUBE_URL" --local --force-stt
```

If an `.env` file is used locally:

```bash
uv run --env-file .env scripts/prepare.py "YOUTUBE_URL"
```

`prepare.py` prints the final `downloads/<title>/manifest.json` path.

## Inputs

- `url`: one YouTube URL.
- `--languages ko,en`: preferred subtitle languages.
- `--local`: use local `faster-whisper` instead of ElevenLabs.
- `--force-stt`: ignore downloaded subtitles and run STT.
- `--keyterms context/interests.md`: optional Scribe v2 keyterm bias file.
- `--max-comments 100`: retain top comments for insight extraction.
- `--max-frames 50`: cap representative frames.

Use `ELEVENLABS_API_KEY` from the environment for public-video STT. Never write secrets to code, manifests, logs, or summaries.

## Workflow

1. **Prepare assets**
   - Run `scripts/prepare.py` with the URL.
   - Use `--local` for private or internal content.
   - Wait for `manifest.json`.

2. **Read receipts first**
   - Read only `manifest.json`.
   - Note metadata, transcript source, frame count, comments path, context file paths, and prompt paths.
   - Do not load the full transcript or all frames at once.

3. **Check relevance**
   - Read `prompts/relevance_check.md`.
   - Read only the concise `context/*.md` files needed for the topic.
   - Use title, description, comments, and the first transcript excerpt to produce:

```json
{
  "relevance_score": 0,
  "matched_topics": [],
  "summary_mode": "generic"
}
```

Mode thresholds:
- `7-10`: `contextual`
- `4-6`: `hybrid`
- `0-3`: `generic`

4. **Analyze frames in small batches**
   - Open frames listed in `manifest.json` only when they look useful by timestamp, reason, or nearby transcript.
   - Analyze 8-12 frames per batch for long videos.
   - For each useful frame, record timestamp, visible content, on-screen text, and why it matters.
   - Distinguish visual evidence from transcript evidence.

5. **Compress scene notes**
   - Combine nearby frames and transcript segments into scene-level notes.
   - Keep notes short enough for one final synthesis pass.
   - Preserve timestamps and frame paths for traceability.

6. **Write the final summary**
   - Use `prompts/generic_summary.md` for `generic`.
   - Use `prompts/contextual_summary.md` for `hybrid` or `contextual`.
   - Write Korean Markdown with YAML frontmatter.
   - Include clickable timestamps using `URL&t=<seconds>s`.
   - Add comment insights when comments are available.
   - Save to the user-requested output directory or the work folder as `summary.md`.

## Output Contract

The final Markdown summary must include:

- YAML frontmatter with title, channel, URL, upload date, duration, views, likes, tags, summary mode, matched topics, captured frame count, and generation time.
- `## 핵심 요약`
- `## 챕터별 상세 (with 비주얼)`
- `## 한컴 적용 포인트` only for `hybrid` or `contextual`
- `## 댓글 인사이트`

## Failure Handling

- If subtitles are missing or too short, use STT fallback.
- If `ELEVENLABS_API_KEY` is missing for API STT, ask the user to set it or rerun with `--local`.
- If scene detection fails, use uniform sampling from `scene_detect.py`.
- If comments are unavailable, keep the section and state that no useful comments were retrieved.
- If a video is roughly 3 hours or longer and final synthesis becomes too large, summarize by YouTube chapter boundaries with small overlaps and carry forward one-line chapter context.

## Bundled Resources

- `scripts/download.py`: yt-dlp metadata, comments, subtitles, low-resolution video, and audio extraction.
- `scripts/transcribe.py`: subtitle selection plus ElevenLabs Scribe v2 or local faster-whisper fallback.
- `scripts/scene_detect.py`: PySceneDetect, ffmpeg frame extraction, transcript weighting, and imagehash dedupe.
- `scripts/prepare.py`: end-to-end deterministic preparation and manifest generation.
- `context/*.md`: Hancom relevance context.
- `prompts/*.md`: relevance and final-summary templates.
