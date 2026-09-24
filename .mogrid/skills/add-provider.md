---
description: 새 LLM provider를 폴백 라우터에 추가할 때 따라야 할 절차 (클라이언트, 등록, 테스트, 문서)
---

provider를 추가할 때는 아래 순서를 그대로 따른다. 하나라도 빠지면 폴백이 조용히
새 provider를 건너뛰거나, 테스트가 실제 API를 호출해서 무료 할당량을 태운다.

## 1. 클라이언트 파일

`router/<이름>_client.py`를 만든다. 기존 `router/groq_client.py`를 먼저 읽고 그 구조를
그대로 따른다. 반드시 지킬 것:

- API 키는 `os.getenv("<이름>_API_KEY")`로 읽는다. 절대 하드코딩하지 않는다.
- 전용 예외 `<이름>Error(Exception)`를 정의한다.
- 공개 함수는 `call_<이름>(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 30) -> str`
  형태여야 한다. 다른 provider와 인터페이스가 같아야 폴백이 동작한다.
- `DEFAULT_MODEL`을 모듈 상수로 둔다.
- 아래 경우를 각각 **명시적으로** 처리한다 (silent fail 금지):
  키 없음 / Timeout / ConnectionError / 401 / 429 / 5xx / 그 외 비200 /
  응답 형식 이상 / content가 비어 있음(reasoning 모델이 답을 안 낸 경우).

## 2. 폴백 라우터에 등록

`router/fallback.py`의 `PROVIDERS` 리스트에 `("<이름>", call_<이름>, <이름>Error)`를 추가한다.
이걸 빼먹으면 클라이언트는 멀쩡한데 아무도 호출하지 않는다.

`main.py`의 `_PROVIDER_DISPLAY_NAMES`에도 표시용 이름을 추가한다 (`mogrid status`에 뜬다).

## 3. 모델 가용성 체크

`router/health_check.py`에 `check_<이름>()`을 추가하고 `ALL_CHECKS`에 넣는다.
응답이 OpenAI 호환(`{"data": [{"id": ...}]}`)이면 `_check_openai_style_models()`를 재사용한다.

## 4. 키 설정 마법사

`main.py`의 `PROVIDER_SETUP`에 `("<이름>_API_KEY", "표시 이름", "키 발급 URL")`을 추가한다.

## 5. 테스트

`tests/test_<이름>_client.py`를 만든다. `tests/test_groq_client.py`와 같은 케이스를 덮는다.
**반드시 `unittest.mock`으로 `requests.post`를 모킹한다** — 실제 네트워크 호출이나 키 소모가
있으면 안 된다. `tests/helpers.py`의 `FakeResponse`를 쓴다.

`router.fallback`을 테스트한다면 개별 `call_*`가 아니라 `router.fallback.PROVIDERS` 자체를
패치해야 한다 (import 시점에 함수 참조가 캡처되므로).

## 6. 확인

```bash
python3 -m unittest discover -s tests -t .
```

전부 통과하면 `mogrid check-models`로 방금 넣은 DEFAULT_MODEL이 실제로 살아있는지 확인한다.

## 7. 문서

`CLAUDE.md`의 "프로젝트 목적" provider 목록과 "폴더 구조" router/ 설명을 갱신한다.
