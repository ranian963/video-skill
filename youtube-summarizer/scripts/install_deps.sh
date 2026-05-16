#!/usr/bin/env bash
set -euo pipefail

echo "YouTube Summarizer dependency check"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it from https://docs.astral.sh/uv/"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is not installed. On macOS, run: brew install ffmpeg"
  exit 1
fi

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffprobe is not installed. It is included with ffmpeg."
  exit 1
fi

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "yt-dlp is not installed as a command. uv-managed scripts can still import yt-dlp."
else
  echo "yt-dlp: $(yt-dlp --version)"
fi

echo "uv: $(uv --version)"
echo "ffmpeg: $(ffmpeg -version 2>/dev/null | head -n 1)"
echo "Dependency check complete."
