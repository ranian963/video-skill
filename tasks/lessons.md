# Lessons

- `quick_validate.py` depends on `PyYAML`; run it with `uv run --with pyyaml ...` when the base Python environment does not have `yaml`.
- `scenedetect[opencv]` emits an extra-name warning with current PySceneDetect 0.7 packaging; declare `scenedetect` and `opencv-python-headless` separately.
- Subtitle fallback should accept a short subtitle when no audio file is available, instead of failing before STT can run.
- Real YouTube E2E smoke test passed with `https://www.youtube.com/watch?v=jNQXAC9IVRw`: manual subtitles produced 6 transcript segments, scene extraction produced 2 frames, and `manifest.json` was generated under `/tmp`.
- ElevenLabs Scribe v2 fallback was verified on the same public YouTube test video with `--force-stt --language en`: it produced `stt:elevenlabs-scribe-v2`, 4 transcript segments, 1 extracted frame, and a final `manifest.json`.
- Local video input should not copy the source video into `downloads/`; keep `source_path` and `files.video` pointed at the original file, then store derived audio, frames, and manifests in the work directory.
- Local video end-to-end verification passed with a generated speech mp4: `source_type=local_file`, Scribe v2 produced 1 transcript segment, scene extraction produced 1 frame, and dimensions were recorded as 320x180.
- Some YouTube `source.info.json` metadata and ffmpeg stderr can contain non-UTF-8 bytes; decode JSON receipts and captured subprocess output with `errors="replace"` so frame extraction and manifest creation do not silently lose all frames.
