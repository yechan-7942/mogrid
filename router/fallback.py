from router.gemini_client import GeminiError, call_gemini
from router.groq_client import GroqError, call_groq
from router.mistral_client import MistralError, call_mistral
from router.nvidia_client import NvidiaError, call_nvidia
from router.ollama_client import OllamaError, call_ollama
from router.openrouter_client import OpenRouterError, call_openrouter
from router.usage import record_failure, record_success

PROVIDERS = [
    ("groq", call_groq, GroqError),
    ("gemini", call_gemini, GeminiError),
    ("openrouter", call_openrouter, OpenRouterError),
    ("mistral", call_mistral, MistralError),
    ("nvidia", call_nvidia, NvidiaError),
    ("ollama", call_ollama, OllamaError),
]


class AllProvidersFailedError(Exception):
    pass


# 매 호출마다 시작 provider를 한 칸씩 돌려서, 맨 앞(groq)으로 부하가 쏠려 그 provider만
# 레이트리밋에 먼저 도달하는 걸 막는다. 실패 시에는 여전히 나머지 provider를 순서대로
# 전부 시도한다 — 시작점만 바뀔 뿐 폴백 커버리지는 그대로.
_rotation = 0


def _reset_rotation() -> None:
    global _rotation
    _rotation = 0


def call_llm(prompt: str) -> str:
    global _rotation
    failures = []
    n = len(PROVIDERS)
    start = _rotation % n
    _rotation += 1
    order = PROVIDERS[start:] + PROVIDERS[:start]

    for name, call_fn, error_cls in order:
        try:
            result = call_fn(prompt)
        except error_cls as e:
            # 개별 provider 실패는 폴백이 있으니 정상 동작의 일부다 — 화면에 찍지 않는다.
            # 버려지는 건 아니고, 남은 provider가 전부 실패했을 때 던지는
            # AllProvidersFailedError와 usage.json(`mogrid status`)에 그대로 남는다.
            error_text = str(e)
            failures.append(f"{name}: {error_text}")
            record_failure(name, error_text)
            continue
        record_success(name)
        return result

    raise AllProvidersFailedError(
        "모든 provider가 실패했습니다.\n" + "\n".join(failures)
    )


if __name__ == "__main__":
    result = call_llm("한 문장으로 너를 소개해줘.")
    print(result)
