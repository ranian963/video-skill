# YouTube 종합 요약 Skill 설계 요약

## 목표
유튜브 URL 1건을 입력하면 자막, 메타데이터, 댓글, 화면 프레임, 한컴 컨텍스트를 함께 사용해 한국어 마크다운 요약을 생성하는 Claude Code/Codex 호환 Skill을 만든다.

## 아키텍처
결정론적이고 무거운 작업은 `scripts/prepare.py`가 처리한다. `prepare.py`는 다운로드, 자막/STT, 씬 감지, 프레임 추출, 중복 제거를 실행하고 `downloads/<title>/manifest.json`을 만든다. 실행 주체는 `SKILL.md` 절차에 따라 manifest를 먼저 읽고, 필요한 프레임만 열어 씬별 분석과 통합 요약을 작성한다.

## 핵심 정책
- 무거운 데이터는 디스크에 두고 컨텍스트에는 파일 경로, 타임스탬프, 크기 같은 영수증만 올린다.
- 자막 fallback은 사람 자막, 자동 자막, ElevenLabs Scribe v2, `--local` faster-whisper 순서로 처리한다.
- 공개 유튜브 영상은 API STT를 허용하고, 사내/비공개 영상은 `--local`로 외부 유출을 막는다.
- 씬 감지는 PySceneDetect `ContentDetector`와 `AdaptiveDetector`를 함께 사용하고, 분당 2장, 하한 12장, 상한 50장 정책과 perceptual hash 중복 제거를 적용한다.
- 회사 컨텍스트는 v1에서 `context/` 정적 마크다운으로 유지한다.

## 산출물
- `youtube-summarizer/SKILL.md`
- `youtube-summarizer/scripts/`
- `youtube-summarizer/context/`
- `youtube-summarizer/prompts/`
- `youtube-summarizer/.env.example`
- `youtube-summarizer/.gitignore`
- `youtube-summarizer/agents/openai.yaml`
- `youtube-summarizer/.claude-plugin/plugin.json`
