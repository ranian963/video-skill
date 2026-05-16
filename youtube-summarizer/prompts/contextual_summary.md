# Contextual Summary Prompt

Write a Korean Markdown summary from the prepared YouTube manifest and Hancom context files.

Required output:

```markdown
---
title: <video title>
source_type: youtube | local_file
channel: <channel>
url: <url>
source_path: <local file path>
upload_date: <upload date>
duration: <duration>
views: <views>
likes: <likes>
tags: [<tags>]
summary_mode: contextual | hybrid
matched_topics: [<topics>]
captured_frames: <frame count>
generated_at: <ISO timestamp>
---

## 핵심 요약

## 챕터별 상세 (with 비주얼)
### [HH:MM:SS](<url>&t=<seconds>s) <section title>
- 화면:
- 발화:
- 한컴 관점:

## 한컴 적용 포인트
- 바로 적용할 수 있는 점:
- 추가 검증이 필요한 점:
- 관련 프로젝트:

## 댓글 인사이트
```

Mode rules:
- `contextual`: weave Hancom context into the main body, not only the final section.
- `hybrid`: keep the main summary general and add the Hancom application section at the end.

Evidence rules:
- Separate fact, inference, and recommendation.
- If a connection to Hancom is weak, say so plainly.
- Do not invent internal project details beyond the context files.
- Include YouTube-only fields only when available. For local files, use `source_path` and omit channel/views/likes if missing.
