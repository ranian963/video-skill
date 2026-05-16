# Generic Summary Prompt

Write a Korean Markdown summary from the prepared YouTube manifest.

Required output:

```markdown
---
title: <video title>
channel: <channel>
url: <url>
upload_date: <upload date>
duration: <duration>
views: <views>
likes: <likes>
tags: [<tags>]
summary_mode: generic
matched_topics: []
captured_frames: <frame count>
generated_at: <ISO timestamp>
---

## 핵심 요약

## 챕터별 상세 (with 비주얼)
### [HH:MM:SS](<url>&t=<seconds>s) <section title>
- 화면:
- 발화:

## 댓글 인사이트
```

Rules:
- Summarize in Korean even when the video is in another language.
- Use visual frame analysis when frames contain slides, UI, products, code, diagrams, or on-screen text.
- Do not paste the full transcript.
- Distinguish what is visible on screen from what is said in the transcript.
- Include viewer-known issues, highlights, or warnings from comments when available.
