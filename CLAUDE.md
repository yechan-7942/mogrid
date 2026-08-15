# Mogrid

## 프로젝트 목적
무료 LLM API(Groq, Gemini, OpenRouter)를 여러 개 묶어서, CLI 환경에서 파일을
읽고 쓰며 계속 작업을 이어가는 에이전트 도구. 하나의 provider가
실패하면 다음 provider로 자동 전환되는 폴백 라우터가 핵심.

## 현재 단계
MVP 완성 — 폴백 라우터(groq→gemini→openrouter), tool 6종, 에이전틱 루프,
CLI 진입점(`main.py`), 디스크 기반 세션 영속성, unittest 테스트 스위트까지 구현됨.

## 폴더 구조
- router/    : provider별 API 클라이언트 + 폴백 로직 (groq, gemini, openrouter)
- agent_loop/: 요청-응답-tool실행 루프 + 세션 영속성(session.py)
- tools/     : 모델이 호출할 수 있는 함수들 (list_files, read_file, write_file,
  append_file, make_dir, search_files)
- tests/     : unittest 테스트 스위트 (provider별, tool별, agent_loop, session)
- main.py    : CLI 진입점 (한 번 실행 모드 / 대화형 모드)

## 규칙
- API 키는 항상 .env에서 읽고, 하드코딩 금지
- 각 provider 클라이언트는 같은 인터페이스(call_모델명(prompt) -> str)를 따를 것
- 에러 처리는 항상 명시적으로, silent fail 금지
- 무료 티어 모델 이름/가용성은 자주 바뀌므로, 코드나 문서 기억에 의존하지 말고
  각 provider의 `/models` 목록을 실제로 조회해서 확인할 것

## 테스트
```bash
python3 -m unittest discover -s tests -t .
```
전부 `unittest.mock`으로 외부 API(`requests.post`)를 모킹함 — 실제 네트워크 호출이나
API 키 소모 없이 실행됨. `router.fallback`을 테스트할 때는 개별 `call_*` 함수가 아니라
`router.fallback.PROVIDERS` 자체를 패치해야 한다 (import 시점에 함수 참조가 캡처되므로).

## 다음 단계
현재 특별히 지정된 다음 단계 없음 — 사용자 지시에 따라 진행 (예: 4번째 provider,
agent_loop 개선, Notion 문서화, git push 등).
