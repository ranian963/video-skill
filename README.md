# YouTube 종합 요약 Skill

YouTube URL 또는 로컬 영상 파일 하나를 입력하면 자막/STT, 메타데이터, 댓글, 화면 프레임을 준비하고, Codex가 이를 바탕으로 한국어 마크다운 요약을 작성할 수 있게 해주는 Skill입니다.

핵심 흐름은 단순합니다. 무거운 영상, 오디오, 자막, 프레임 파일은 디스크에 저장하고, Codex는 `manifest.json`을 먼저 읽은 뒤 필요한 파일만 열어 최종 요약을 작성합니다.

## 현재 지원 범위

- YouTube URL 또는 로컬 영상 파일 1건 처리
- YouTube 영상은 제목, 채널, 업로드일, 길이, 조회수, 좋아요, 태그, 설명 수집
- 로컬 영상은 파일명, 경로, 길이, 해상도, 코덱, 파일 크기 수집
- 사람 자막 우선 사용, 없거나 강제 지정 시 STT fallback
- ElevenLabs Scribe v2 Batch 기반 STT
- 씬 변화와 자막 힌트를 이용한 대표 프레임 추출
- imagehash 기반 중복 프레임 제거
- 좋아요 상위 댓글 수집
- 최종 요약을 위한 `manifest.json` 생성

## 필요한 것

| 구분 | 필요 항목 |
|---|---|
| 실행 환경 | macOS |
| 에이전트 | Codex Desktop 또는 Codex CLI |
| 기본 도구 | `uv`, `ffmpeg`, `ffprobe`, `yt-dlp` |
| Python | `uv`가 스크립트별 의존성을 자동 구성 |
| STT API | `ELEVENLABS_API_KEY` |

## API 키 설정

ElevenLabs API 키는 코드에 넣지 않습니다. 셸 환경변수나 `youtube-summarizer/.env` 파일로만 관리합니다.

```bash
export ELEVENLABS_API_KEY="..."
```

이 저장소에는 템플릿만 커밋합니다.

```text
youtube-summarizer/
├── .env.example   # 커밋 가능
└── .env           # 커밋 금지
```

## 설치 확인

```bash
cd /Users/chester/dev/video-skill/youtube-summarizer
bash scripts/install_deps.sh
```

성공하면 `uv`, `ffmpeg`, `yt-dlp` 버전이 출력됩니다.

## 기본 사용법

자막이 있는 공개 YouTube 영상은 기본 명령으로 처리합니다.

```bash
cd /Users/chester/dev/video-skill/youtube-summarizer
uv run scripts/prepare.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

실행이 끝나면 아래처럼 최종 manifest 경로가 출력됩니다.

```text
downloads/<video-title>-<video-id>/manifest.json
```

로컬 영상 파일은 파일 경로를 그대로 넘깁니다. 로컬 영상은 YouTube 자막이 없으므로 기본적으로 ElevenLabs STT 경로를 사용합니다.

```bash
uv run scripts/prepare.py "/path/to/video.mp4" --language ko
```

## STT 강제 사용

자막 대신 ElevenLabs Scribe v2로 STT를 강제로 검증하거나 사용하려면 `--force-stt`를 붙입니다. 영상 언어에 맞춰 `--language`도 지정하는 편이 좋습니다.

```bash
uv run scripts/prepare.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --force-stt \
  --language en
```

`.env` 파일을 쓰는 경우:

```bash
uv run --env-file .env scripts/prepare.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --force-stt \
  --language en
```

## 자주 쓰는 옵션

| 옵션 | 기본값 | 설명 |
|---|---:|---|
| `--output-root downloads` | `downloads` | 산출물 루트 디렉터리 |
| `--languages ko,en` | `ko,en` | 자막 언어 우선순위 |
| `--language ko` | `ko` | STT 언어 코드. 영어 영상은 `en` 권장 |
| `--max-comments 100` | `100` | 수집할 댓글 수 |
| `--max-height 480` | `480` | 다운로드할 영상 최대 높이 |
| `--force-stt` | off | 자막을 무시하고 STT 실행 |
| `--min-frames 12` | `12` | 최소 캡처 프레임 수 |
| `--max-frames 50` | `50` | 최대 캡처 프레임 수 |

## 산출물 구조

```text
downloads/<video-title>-<video-id>/
├── manifest.json              # Codex가 먼저 읽을 최종 manifest
├── download_manifest.json     # 다운로드 단계 manifest
├── frames_manifest.json       # 프레임 추출 결과
├── transcript.json            # 세그먼트 포함 transcript
├── transcript.txt             # plain text transcript
├── transcript.vtt             # timestamp transcript
├── comments.json              # 댓글이 있으면 생성
├── source.info.json           # yt-dlp metadata
├── source.mp4                 # 저해상도 영상
├── audio.wav                  # STT용 오디오
└── frames/
    └── frame_*.jpg
```

`downloads/`, `.env`, 영상, 오디오, 프레임 파일은 Git에 올리지 않습니다.

로컬 영상 파일은 `downloads/`로 복사하지 않습니다. `manifest.json`의 `files.video`와 `source_path`가 원본 파일 경로를 가리킵니다.

## 최종 요약 작성 흐름

`prepare.py`는 최종 요약 문서까지 쓰지 않습니다. 준비가 끝나면 Codex가 다음 순서로 작업합니다.

1. `manifest.json`을 먼저 읽습니다.
2. 필요한 transcript 구간과 frame 이미지만 엽니다.
3. `prompts/relevance_check.md`로 요약 모드를 정합니다.
4. `prompts/generic_summary.md` 또는 `prompts/contextual_summary.md`에 맞춰 `summary.md`를 작성합니다.

최종 요약은 frontmatter가 포함된 마크다운입니다.

```markdown
---
title: 영상 제목
source_type: youtube | local_file
channel: 채널명
url: 영상 URL
source_path: 로컬 파일 경로
upload_date: 업로드일
duration: 영상 길이
views: 조회수
likes: 좋아요 수
summary_mode: generic | hybrid | contextual
captured_frames: 캡처 프레임 수
generated_at: 생성 시각
---

## 핵심 요약

## 챕터별 상세 (with 비주얼)

## 적용 포인트

## 댓글 인사이트
```

## 실제 검증 결과

2026-05-16 기준으로 아래 경로를 실제 실행해 확인했습니다.

### 기본 자막 경로

```bash
uv run youtube-summarizer/scripts/prepare.py \
  "https://www.youtube.com/watch?v=jNQXAC9IVRw" \
  --output-root /tmp/youtube-summarizer-real-test \
  --languages en,ko \
  --max-comments 0 \
  --max-height 360 \
  --min-subtitle-chars 1 \
  --min-frames 2 \
  --max-frames 4
```

결과:
- `manifest.json` 생성 성공
- transcript source: `subtitle:manual`
- transcript segments: `6`
- extracted frames: `2`

### ElevenLabs STT 경로

```bash
uv run youtube-summarizer/scripts/prepare.py \
  "https://www.youtube.com/watch?v=jNQXAC9IVRw" \
  --output-root /tmp/youtube-summarizer-scribe-test \
  --languages en \
  --language en \
  --max-comments 0 \
  --max-height 360 \
  --force-stt \
  --min-frames 1 \
  --max-frames 2
```

결과:
- `manifest.json` 생성 성공
- transcript source: `stt:elevenlabs-scribe-v2`
- transcript segments: `4`
- extracted frames: `1`

### 로컬 영상 파일 경로

테스트용 말소리 포함 mp4 파일을 만든 뒤 로컬 입력 전체 경로를 실행했습니다.

```bash
uv run youtube-summarizer/scripts/prepare.py \
  "/tmp/youtube-summarizer-local-e2e/local-sample.mp4" \
  --output-root /tmp/youtube-summarizer-local-e2e/out \
  --language en \
  --min-frames 1 \
  --max-frames 2
```

결과:
- `manifest.json` 생성 성공
- `source_type`: `local_file`
- `files.video`가 원본 `source_path`를 가리킴
- transcript source: `stt:elevenlabs-scribe-v2`
- transcript segments: `1`
- extracted frames: `1`
- width/height metadata: `320x180`

## 주의할 점

- API 키가 코드, 로그, manifest에 찍히지 않게 합니다.
- `yt-dlp`가 YouTube JS challenge 경고를 출력할 수 있습니다. 테스트에서는 경고가 있었지만 다운로드와 manifest 생성은 성공했습니다.
- 영어 영상은 STT 실행 시 `--language en`처럼 실제 영상 언어를 지정하는 것이 좋습니다.
- 긴 영상은 다운로드, STT, 프레임 추출 시간이 길어질 수 있습니다.
