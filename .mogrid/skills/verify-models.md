---
description: 무료 티어 모델 이름을 고르거나 바꿀 때, 기억에 의존하지 않고 실제 목록을 조회해서 확인하는 방법
---

무료 티어 모델 이름과 가용성은 자주 바뀐다. 학습 지식이나 코드에 적힌 기존 값,
문서에 적힌 값을 근거로 모델 이름을 고르지 마라 — **반드시 실제 목록을 조회해서 확인한다.**

## 먼저 할 일

```bash
python3 main.py check-models
```

이게 각 provider의 `/models`를 실제로 조회해서 현재 `DEFAULT_MODEL`이 아직 존재하는지
확인해준다. 결과가 전부 OK면 바꿀 게 없다. 여기서 끝내고 그 사실을 보고해라.

## 모델이 `누락`으로 나온 경우

그 provider의 모델 목록을 직접 받아서 대체할 후보를 고른다. OpenAI 호환 provider
(Groq, Mistral, NVIDIA NIM, OpenRouter)는 아래 형태로 조회한다:

```bash
python3 -c "
import os, requests
from dotenv import load_dotenv
load_dotenv()
r = requests.get('<MODELS_URL>', headers={'Authorization': f\"Bearer {os.getenv('<KEY_ENV>')}\"}, timeout=20)
print(r.status_code)
for m in r.json()['data']:
    print(m['id'])
"
```

- Groq: `https://api.groq.com/openai/v1/models` / `GROQ_API_KEY`
- Mistral: `https://api.mistral.ai/v1/models` / `MISTRAL_API_KEY`
- NVIDIA NIM: `https://integrate.api.nvidia.com/v1/models` / `NVIDIA_API_KEY`
- OpenRouter: `https://openrouter.ai/api/v1/models` (키 없이도 조회 가능, 무료는 `:free` 접미사)

Gemini는 형태가 다르다: `https://generativelanguage.googleapis.com/v1beta/models`에
`x-goog-api-key` 헤더를 쓰고, 응답은 `{"models": [{"name": "models/..."}]}`.

Ollama는 로컬이다: `curl http://localhost:11434/api/tags`.

## 고른 뒤

1. 해당 `router/*_client.py`의 `DEFAULT_MODEL`을 바꾼다.
2. embedding/reranking/vision 전용 모델을 채팅용으로 고르지 않았는지 확인한다
   (이름에 `embed`, `rerank`, `parse`, `guard`, `safety`, `vision`이 들어가면 대개 아니다).
3. `python3 main.py check-models`를 다시 돌려서 OK가 나오는지 확인한다.
4. 실제로 한 번 호출해서 답이 오는지까지 확인한다:
   `python3 -c "from router.<이름>_client import call_<이름>; print(call_<이름>('안녕'))"`
