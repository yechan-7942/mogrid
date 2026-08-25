# Mogrid

## 프로젝트 목적
무료 LLM API(Groq, Gemini, OpenRouter, Mistral, NVIDIA NIM) + 로컬 LLM(Ollama)을
여러 개 묶어서, CLI 환경에서 파일을 읽고 쓰며 계속 작업을 이어가는 에이전트 도구.
하나의 provider가 실패하면 다음 provider로 자동 전환되는 폴백 라우터가 핵심.

## 현재 단계
MVP 완성 이후 Claude Code에 준하는 수준으로 고도화 진행 중 — 폴백 라우터
(groq→gemini→openrouter→mistral→nvidia→ollama), tool 8종(edit_file 포함 부분 수정/
정규식 검색/offset·limit 읽기 지원, update_task_list로 다단계 작업 진행 상황 추적),
에이전틱 루프, CLI 진입점(`main.py`, `mogrid` 명령으로 설치 가능), 상한 있는 디스크
기반 세션 영속성, unittest 테스트 스위트 + GitHub Actions CI까지 구현됨.

## 폴더 구조
- router/    : provider별 API 클라이언트 + 폴백 로직 (groq, gemini, openrouter, mistral,
  nvidia, ollama). ollama는 로컬 서버(기본 http://localhost:11434, `OLLAMA_BASE_URL`로
  변경 가능)라 API 키가 없고, 콜드 스타트(모델을 메모리에서 내렸다가 다시 로드) 시
  응답까지 2~3분 걸릴 수 있어 timeout을 다른 provider보다 훨씬 크게 잡아뒀다.
- agent_loop/: 요청-응답-tool실행 루프 + 세션 영속성(session.py, 최근 10턴/항목당 2000자
  상한). 세션 파일은 `MOGRID_PROJECT_ROOT`(없으면 cwd) 기준으로 프로젝트별로 분리되어
  `~/.mogrid/sessions/`에 저장됨 — 서로 다른 프로젝트의 작업 기록이 섞이지 않는다.
  run_command와 "기존 파일 덮어쓰기"(write_file)는 실행 전 `confirm` 콜백으로 확인을
  받는다 — 대화형 모드는 직접 물어보고, 한 번 실행 모드는 기본 차단(`--yes`나
  `MOGRID_AUTO_APPROVE=1`로 해제). confirm을 안 넘기면(테스트 등) 게이팅 자체가 없다.
  session_history가 10개를 넘으면 그냥 자르지 않고 summarizer.py가 넘치는 만큼만
  LLM으로 요약해서 한 항목(`[이전 작업 요약] ...`)으로 압축하고 최근 기록은 그대로
  둔다(`main.py: summarize_session_if_needed`) — 요약 자체가 실패하면(전체 provider
  장애 등) 기존 방식(그냥 자르기)으로 안전하게 폴백한다.
- tools/     : 모델이 호출할 수 있는 함수들 (list_files, read_file, write_file,
  edit_file, append_file, make_dir, search_files, update_task_list). task_tracker.py는
  exec_tools.py의 `_PROCESSES`와 같은 패턴으로 모듈 전역 상태를 쓰고, run_agent() 시작
  시 매번 reset된다 (작업 간 하위 작업 목록이 새지 않게).
- tests/     : unittest 테스트 스위트 (provider별, tool별, agent_loop, session)
- main.py    : CLI 진입점 (한 번 실행 모드 / 대화형 모드)
- pyproject.toml: `pip install -e .`로 설치하면 `mogrid` 명령 사용 가능
- .github/workflows/test.yml: push/PR마다 테스트 스위트 자동 실행

## 규칙
- API 키는 항상 .env에서 읽고, 하드코딩 금지
- 각 provider 클라이언트는 같은 인터페이스(call_모델명(prompt) -> str)를 따를 것
- 에러 처리는 항상 명시적으로, silent fail 금지
- 무료 티어 모델 이름/가용성은 자주 바뀌므로, 코드나 문서 기억에 의존하지 말고
  각 provider의 `/models` 목록을 실제로 조회해서 확인할 것

## 설치 / 실행
```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .
mogrid setup                # provider API 키 설정 마법사 (브라우저로 발급 페이지를 열어줌)
mogrid                      # 대화형 모드
mogrid "작업 설명"           # 한 번 실행 모드
```
`venv/`는 `.gitignore`에 포함되어 있음 — 로컬 개발용으로만 생성.
`mogrid setup`은 로그인/키 발급은 사용자가 직접 하게 하고, 발급 페이지를 여는 것과
받은 키를 `.env`에 저장하는 것만 자동화한다 — 로그인 자격 증명을 다루지 않는다.

## 테스트
```bash
python3 -m unittest discover -s tests -t .
```
전부 `unittest.mock`으로 외부 API(`requests.post`)를 모킹함 — 실제 네트워크 호출이나
API 키 소모 없이 실행됨. `router.fallback`을 테스트할 때는 개별 `call_*` 함수가 아니라
`router.fallback.PROVIDERS` 자체를 패치해야 한다 (import 시점에 함수 참조가 캡처되므로).
push/PR마다 GitHub Actions(`.github/workflows/test.yml`)에서도 동일하게 실행됨.

## 다음 단계
"Claude Code에 준하는 수준으로" 고도화 로드맵 5개(edit_file, search/read 개선,
task tracking, 위험 행동 확인, 세션 요약) 완료. 현재 특별히 지정된 다음 단계 없음 —
사용자 지시에 따라 진행 (예: agent_loop의 간접/우회 표현 작업 지시 처리 한계 개선,
Notion 문서화 등).
