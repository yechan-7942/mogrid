# Mogrid

[![test](https://github.com/yechan-7942/mogrid/actions/workflows/test.yml/badge.svg)](https://github.com/yechan-7942/mogrid/actions/workflows/test.yml)

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

### 예시

```
$ mogrid "notes.txt에 '리팩터링 아이디어: 세션 요약 개선' 한 줄을 추가하고 git status로 확인해줘"

[groq 실패 → gemini로 전환]
[tool] append_file(path="notes.txt", content="리팩터링 아이디어: 세션 요약 개선\n")
[확인 필요] run_command 실행: git status
계속하시겠습니까? [y/N]: y
[tool] run_command(command="git status")
  → 출력: notes.txt 수정됨 (unstaged)

notes.txt에 한 줄을 추가했고, git status로 반영된 것을 확인했습니다.
```

첫 provider(groq)가 실패해도 라우터가 자동으로 gemini로 넘어가고, 기존 내용을
보존하는 `append_file`은 확인 없이 바로 실행되지만 `run_command`는 확인을 거친다.

## 테스트

```bash
python3 -m unittest discover -s tests -t .
```

전부 `unittest.mock`으로 외부 API를 모킹해서, 실제 네트워크 호출이나 API 키
소모 없이 돌아간다. push/PR마다 GitHub Actions에서도 동일하게 실행된다.

## 알려진 한계

무료/약한 모델을 여러 개 체인으로 묶는 구조라서, 유료 프론티어 모델 하나를 쓰는
것과는 다른 종류의 실패가 발생한다.

- **간접적으로 표현된 작업 지시에 약하다.** "시스템 프롬프트를 만드는 함수를
  찾아줘"처럼 함수/파일 이름을 직접 언급하지 않고 돌려 말하면, 폴더를 체계적으로
  탐색하지 못하고 엉뚱한 파일을 헤매는 경우가 있다. 프롬프트 규칙 몇 개로 고쳐지지
  않는, 약한 모델 자체의 한계로 확인됨.
- **코드를 직접 수정하는 대신 설명만 하고 끝내는 경우가 있다.** tool을 호출하지
  않고 코드를 텍스트로만 보여주고 끝내는 사례가 실사용 중 발견됨 — 아직 고치지
  않은 상태.
- **무료 티어 모델 로스터가 자주 바뀐다.** provider가 기본으로 쓰던 모델이 며칠 뒤
  통째로 사라지거나(404) 유료 전환되는 일이 흔하다. 코드에 적힌 모델 이름을 그대로
  믿지 말고, 새로 셋업할 때는 각 provider의 `/models` 목록을 실제로 조회해서 확인할 것.
- **추론(reasoning) 모델은 최종 답을 빈 문자열로 반환할 때가 있다.** 추론 토큰이
  응답 예산을 다 써버리면 `content`가 비어서 반환되는 provider가 있음 — 이런 경우
  해당 provider 호출을 명시적으로 실패 처리하고 다음 provider로 넘기도록 처리되어
  있지만, 근본적으로는 모델 쪽 특성이라 새 provider/모델을 추가할 때마다 같은 문제가
  재발할 수 있다.

## 참고

- Ollama는 로컬 서버(기본 `http://localhost:11434`)라 API 키가 없고, 콜드 스타트
  시 응답까지 2~3분 걸릴 수 있어 timeout을 다른 provider보다 훨씬 크게 잡아뒀다.
