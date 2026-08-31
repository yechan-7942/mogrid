# Mogrid

무료 LLM API(Groq, Gemini, OpenRouter, Mistral, NVIDIA NIM) + 로컬 LLM(Ollama)을
여러 개 묶어서, CLI 환경에서 파일을 읽고 쓰며 계속 작업을 이어가는 에이전트 도구.
하나의 provider가 실패하면 다음 provider로 자동 전환되는 폴백 라우터가 핵심.

## 왜 만들었나

유료 API 없이도 Claude Code 같은 방식으로 "터미널에서 말로 작업을 시키면 파일을
직접 읽고 고치는" 경험을 만들어보고 싶어서 시작한 개인 프로젝트. 무료 티어 하나만
쓰면 rate limit이나 서버 오류에 바로 막히기 때문에, provider를 여러 개 체인으로
묶어서 하나가 죽어도 다음 걸로 자동으로 넘어가게 만들었다.

## 핵심 동작

1. 작업을 요청하면 agent loop가 모델에게 프롬프트 + tool 목록을 보낸다.
2. 모델이 `{"tool": ..., "args": ...}` 형태로 tool 호출을 반환하면 실제로 실행하고,
   결과를 다시 모델에 넘겨서 다음 스텝을 이어간다.
3. provider 하나가 실패(타임아웃, 빈 응답, 서버 에러 등)하면 라우터가 자동으로
   다음 provider로 전환한다: `groq → gemini → openrouter → mistral → nvidia → ollama`
4. `run_command`나 기존 파일을 덮어쓰는 작업처럼 되돌리기 어려운 행동은 실행 전에
   확인을 받는다.
5. 세션 기록은 프로젝트 디렉토리별로 분리해서 저장하고, 너무 길어지면 통째로
   자르는 대신 넘치는 만큼만 LLM으로 요약해서 압축한다.

## 폴더 구조

| 경로 | 역할 |
|---|---|
| `router/` | provider별 API 클라이언트 + 폴백 로직 |
| `agent_loop/` | 요청-응답-tool실행 루프, 세션 영속성/요약 |
| `tools/` | 모델이 호출할 수 있는 함수들 (파일 조작, 명령 실행, 작업 추적) |
| `tests/` | unittest 테스트 스위트 (provider별, tool별, agent_loop, session) |
| `main.py` | CLI 진입점 (한 번 실행 모드 / 대화형 모드 / `setup`) |
| `.github/workflows/test.yml` | push/PR마다 테스트 스위트 자동 실행 |

## 설치

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

API 키를 발급받아 `.env`에 넣어야 한다. `mogrid setup`을 실행하면 provider별
키 발급 페이지를 브라우저로 열어주고, 붙여넣은 키를 `.env`에 저장해준다
(로그인/발급은 직접 해야 한다).

```bash
mogrid setup
```

## 사용법

```bash
mogrid                # 대화형 모드
mogrid "작업 설명"     # 한 번 실행 모드
```

한 번 실행 모드에서는 `run_command`, 기존 파일 덮어쓰기 같은 위험한 행동을 기본
차단한다. 확인 없이 바로 실행하려면:

```bash
mogrid "작업 설명" --yes
# 또는
MOGRID_AUTO_APPROVE=1 mogrid "작업 설명"
```

대화형 모드에서는 매번 직접 y/N으로 확인받는다.

## 테스트

```bash
python3 -m unittest discover -s tests -t .
```

전부 `unittest.mock`으로 외부 API를 모킹해서, 실제 네트워크 호출이나 API 키
소모 없이 돌아간다. push/PR마다 GitHub Actions에서도 동일하게 실행된다.

## 참고

- API 키는 항상 `.env`에서 읽고, 하드코딩하지 않는다.
- 무료 티어 모델 이름/가용성은 자주 바뀌므로, 코드나 문서 기억에 의존하지 말고
  각 provider의 `/models` 목록을 실제로 조회해서 확인해야 한다.
- Ollama는 로컬 서버(기본 `http://localhost:11434`)라 API 키가 없고, 콜드 스타트
  시 응답까지 2~3분 걸릴 수 있어 timeout을 다른 provider보다 훨씬 크게 잡아뒀다.
