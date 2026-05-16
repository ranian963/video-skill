# YouTube / 로컬 영상 종합 요약 Skill

YouTube 링크나 로컬 영상 파일 하나로 **자막, 화면, 메타데이터, 댓글 반응**을 함께 읽어 한국어 요약 문서로 정리하는 Codex Skill입니다.

단순히 자막만 줄이는 도구가 아니라, 영상 속 슬라이드, 제품 UI, 코드 화면, 댓글 반응까지 함께 반영해 “나중에 다시 봐도 바로 쓸 수 있는” 마크다운 노트를 만듭니다.

## 할 수 있는 일

- YouTube URL 또는 로컬 영상 파일 1개를 입력받아 마크다운 요약 문서를 만듭니다.
- YouTube 영상은 제목, 채널, 업로드일, 조회수, 설명, 태그를 frontmatter로 정리합니다.
- 로컬 영상은 파일명, 경로, 길이, 해상도, 파일 크기 같은 기본 정보를 frontmatter로 정리합니다.
- 사람 자막이 있으면 우선 사용하고, 없으면 자동 자막을 확인합니다.
- 자막이 없거나 품질이 낮으면 ElevenLabs Scribe v2로 STT를 수행합니다.
- 로컬 영상, 사내 영상, 비공개 영상은 `--local` 옵션으로 로컬 STT를 사용합니다.
- 씬 변화가 있는 구간에서 프레임을 캡처해 화면 정보를 요약에 반영합니다.
- YouTube 영상은 좋아요가 높은 댓글과 반복되는 시청자 반응을 댓글 인사이트로 정리합니다.
- 한컴 프로젝트나 관심 기술과 관련된 영상이면 적용 포인트를 따로 뽑습니다.

## 필요한 것

| 구분 | 필요 항목 |
|---|---|
| 실행 환경 | macOS |
| 에이전트 | Codex Desktop 또는 Codex CLI |
| 기본 도구 | `uv`, `ffmpeg` |
| YouTube 입력 | `yt-dlp` |
| Python | Python 3.11 이상 |
| 외부 STT | `ELEVENLABS_API_KEY` |
| 로컬 STT | `faster-whisper`, large-v3 계열 모델 |

외부 STT는 공개 YouTube 영상에 사용합니다. 로컬 영상, 사내 영상, 비공개 영상, 외부 전송이 부담되는 영상은 `--local`로 처리합니다.

## API 키 설정

ElevenLabs API 키는 코드에 넣지 않습니다. 로컬 셸 또는 `.env` 파일로만 관리합니다.

```bash
export ELEVENLABS_API_KEY="..."
```

현재 환경에서는 `~/.zshrc`에 `ELEVENLABS_API_KEY`가 설정되어 있으면 됩니다.

Skill 폴더에는 아래처럼 템플릿만 둡니다.

```text
youtube-summarizer/
├── .env.example   # 커밋 가능
└── .env           # 커밋 금지
```

`--local` 실행은 ElevenLabs API 키 없이 동작해야 합니다.

## 사용 방법

공개 YouTube 영상은 기본 실행으로 처리합니다.

```bash
cd /Users/chester/dev/video-skill/youtube-summarizer
./scripts/install_deps.sh
uv run --env-file .env scripts/prepare.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

사내 영상이나 비공개 YouTube 영상은 로컬 STT를 사용합니다.

```bash
uv run scripts/prepare.py "https://www.youtube.com/watch?v=VIDEO_ID" --local
```

로컬 영상 파일도 같은 방식으로 처리합니다.

```bash
uv run scripts/prepare.py "/path/to/video.mp4" --local
```

준비 스크립트가 끝나면 `downloads/<video-title-or-filename>/manifest.json`이 생성됩니다. Codex는 이 manifest를 기준으로 필요한 자막, 댓글, 프레임만 열어 최종 요약을 작성합니다.

로컬 영상에는 YouTube 댓글, 조회수, 채널 정보가 없으므로 해당 섹션은 생략하거나 파일 정보로 대체합니다.

## 결과물

최종 결과는 frontmatter가 포함된 마크다운 문서입니다.

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
summary_mode: generic | hybrid | contextual
captured_frames: 캡처 프레임 수
generated_at: 생성 시각
---

## 핵심 요약

## 챕터별 상세

## 한컴 적용 포인트

## 댓글 인사이트
```

영상, 오디오, 자막, 캡처 프레임, 로그, manifest는 `downloads/` 아래에 저장됩니다. 이 파일들은 Git에 올리지 않습니다.

## 요약 모드

| 모드 | 쓰임 |
|---|---|
| `generic` | 일반 영상 요약 |
| `hybrid` | 일반 요약에 한컴 적용 포인트를 추가 |
| `contextual` | 한컴 프로젝트나 기술 맥락 중심으로 재구성 |

영어 영상도 기본 출력은 한국어입니다.

## 주의할 점

- `.env`, 영상, 오디오, 자막, 캡처 프레임, 로그는 커밋하지 않습니다.
- API 키가 코드, 로그, manifest에 찍히지 않게 합니다.
- 공개 YouTube 영상은 외부 STT를 사용할 수 있지만, 로컬/사내/비공개 영상은 `--local`을 사용합니다.
- 로컬 영상은 YouTube 댓글, 조회수, 채널 정보를 가져올 수 없습니다.
- 긴 영상은 처리 시간이 오래 걸릴 수 있습니다.
- 화면 정보가 중요한 영상일수록 캡처 프레임 분석 품질이 중요합니다.
