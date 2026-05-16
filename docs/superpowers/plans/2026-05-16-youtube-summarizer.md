# YouTube Summarizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained `youtube-summarizer` skill that prepares YouTube video assets and guides an agent through visual, transcript, comment, and company-context summary generation.

**Architecture:** Use Python scripts for deterministic preparation and a concise `SKILL.md` for agent judgment. Persist heavy artifacts to `downloads/<title>/` and pass only `manifest.json` receipts into model context.

**Tech Stack:** `uv` inline scripts, `yt-dlp`, `ffmpeg`, ElevenLabs Scribe v2, optional `faster-whisper`, PySceneDetect, Pillow, imagehash.

---

### Task 1: Scaffold Skill

**Files:**
- Create: `youtube-summarizer/SKILL.md`
- Create: `youtube-summarizer/agents/openai.yaml`
- Create: `youtube-summarizer/scripts/`
- Create: `youtube-summarizer/references/`
- Create: `youtube-summarizer/.env.example`
- Create: `youtube-summarizer/.gitignore`

- [ ] Run `init_skill.py youtube-summarizer --path /Users/chester/dev/video-skill --resources scripts,references`.
- [ ] Replace the generated `SKILL.md` template with the final procedure.
- [ ] Add local ignore rules for `.env`, `downloads/`, caches, media artifacts, and generated summaries.
- [ ] Add `.env.example` with empty `ELEVENLABS_API_KEY=`.

### Task 2: Implement Deterministic Scripts

**Files:**
- Create: `youtube-summarizer/scripts/install_deps.sh`
- Create: `youtube-summarizer/scripts/download.py`
- Create: `youtube-summarizer/scripts/transcribe.py`
- Create: `youtube-summarizer/scripts/scene_detect.py`
- Create: `youtube-summarizer/scripts/prepare.py`

- [ ] Implement `install_deps.sh` checks for `uv`, `ffmpeg`, `ffprobe`, and `yt-dlp`.
- [ ] Implement `download.py` to fetch metadata, comments, subtitles, low-resolution video, and audio into `downloads/<safe-title>/`.
- [ ] Implement `transcribe.py` to choose subtitle files first, call ElevenLabs only when needed, and support `--local` faster-whisper.
- [ ] Implement `scene_detect.py` with dual detector scene detection, adaptive frame budget, transcript weighting, ffmpeg frame extraction, and imagehash dedupe.
- [ ] Implement `prepare.py` to orchestrate scripts and write `manifest.json`.

### Task 3: Add Context And Prompts

**Files:**
- Create: `youtube-summarizer/context/company.md`
- Create: `youtube-summarizer/context/projects.md`
- Create: `youtube-summarizer/context/tech_stack.md`
- Create: `youtube-summarizer/context/competitors.md`
- Create: `youtube-summarizer/context/interests.md`
- Create: `youtube-summarizer/prompts/relevance_check.md`
- Create: `youtube-summarizer/prompts/generic_summary.md`
- Create: `youtube-summarizer/prompts/contextual_summary.md`

- [ ] Write concise static company context for relevance matching.
- [ ] Write prompt templates that require Korean output, clickable timestamps, comment insights, and mode-specific sections.

### Task 4: Add Metadata And Validation

**Files:**
- Modify: `youtube-summarizer/agents/openai.yaml`
- Create: `youtube-summarizer/.claude-plugin/plugin.json`
- Modify: `tasks/todo.md`
- Create: `tasks/lessons.md`

- [ ] Ensure `agents/openai.yaml` matches the final skill.
- [ ] Add `.claude-plugin/plugin.json` with MIT attribution to the reference repo pattern.
- [ ] Run `quick_validate.py youtube-summarizer`.
- [ ] Run script syntax/help checks.
- [ ] Confirm `ref/`, `.env`, and generated downloads remain ignored.
