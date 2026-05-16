# YouTube 종합 요약 Skill 작업 계획

## 요구사항 요약
- 유튜브 URL 1건을 입력받아 메타데이터, 댓글, 자막/STT, 씬 프레임, 회사 컨텍스트를 통합한 마크다운 요약 Skill을 만든다.
- 개발 위치는 `/Users/chester/dev/video-skill/youtube-summarizer/`로 둔다.
- 참고 레포는 `/Users/chester/dev/video-skill/ref/` 아래에서만 읽고, `ref/`는 Git 추적에서 제외한다.
- 실제 시크릿은 커밋하지 않고 `ELEVENLABS_API_KEY` 환경변수 또는 로컬 `.env`만 사용한다.

## 구현 계획
- [x] Phase 0: 참고 레포와 skill-creator 구조 확인, 재사용할 패턴 확정
- [x] Phase 1: `youtube-summarizer/` Skill 골격 생성, `.env.example`과 ignore 정책 구성
- [x] Phase 2: `download.py`, `transcribe.py`, `scene_detect.py`, `prepare.py` 구현
- [x] Phase 3: context 5종과 prompt 3종 작성
- [x] Phase 4: `SKILL.md`, `agents/openai.yaml`, `.claude-plugin/plugin.json` 완성
- [x] Phase 5: 정적 검증, 스크립트 help/문법 검증, skill validator 실행
- [x] Phase 6: lessons 기록과 최종 상태 정리

## 수정할 파일
- `youtube-summarizer/SKILL.md`: 실행 주체가 따를 절차 매뉴얼
- `youtube-summarizer/scripts/*.py`: 다운로드, 자막/STT, 씬 감지, 통합 prepare 스크립트
- `youtube-summarizer/context/*.md`: 한컴 관련 정적 컨텍스트
- `youtube-summarizer/prompts/*.md`: relevance와 요약 프롬프트
- `youtube-summarizer/.env.example`, `youtube-summarizer/.gitignore`: 시크릿/산출물 제외
- `youtube-summarizer/agents/openai.yaml`, `youtube-summarizer/.claude-plugin/plugin.json`: 스킬 메타데이터
- `tasks/todo.md`, `tasks/lessons.md`: 작업 추적과 교훈 기록

## 예상 위험 요소
- `yt-dlp` 또는 ElevenLabs API는 네트워크/인증/사내 SSL 환경에 따라 실제 E2E 검증이 막힐 수 있다.
- `faster-whisper` 로컬 검증은 모델 다운로드와 GPU/CPU 환경에 따라 오래 걸릴 수 있다.
- 씬 감지 정책은 영상 유형별 튜닝이 필요하므로 v1에서는 안정적인 기본값과 manifest 근거를 우선한다.
