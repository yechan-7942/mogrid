from router.gemini_client import GeminiError, call_gemini
from router.groq_client import GroqError, call_groq
from router.mistral_client import MistralError, call_mistral
from router.openrouter_client import OpenRouterError, call_openrouter

PROVIDERS = [
    ("groq", call_groq, GroqError),
    ("gemini", call_gemini, GeminiError),
    ("openrouter", call_openrouter, OpenRouterError),
    ("mistral", call_mistral, MistralError),
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
            return call_fn(prompt)
        except error_cls as e:
            print(f"[fallback] {name} 실패, 다음 provider로 전환: {e}")
            failures.append(f"{name}: {e}")

    raise AllProvidersFailedError(
        "모든 provider가 실패했습니다.\n" + "\n".join(failures)
    )


if __name__ == "__main__":
    result = call_llm("한 문장으로 너를 소개해줘.")
    print(result)
