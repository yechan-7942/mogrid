from colors import yellow
from router.gemini_client import GeminiError, call_gemini
from router.groq_client import GroqError, call_groq
from router.mistral_client import MistralError, call_mistral
from router.nvidia_client import NvidiaError, call_nvidia
from router.ollama_client import OllamaError, call_ollama
from router.openrouter_client import OpenRouterError, call_openrouter

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


# reasoning 모델이 content를 비우고 실패하면, 에러 메시지에 raw 응답 전체(추론 토큰
# 수천 자 포함)가 그대로 담겨서 매 폴백 hop마다 터미널이 도배된다. 실패 원인을 아는
# 데는 앞부분이면 충분하므로, 화면에 찍을 때만 잘라낸다 — 전부 실패했을 때 던지는
# AllProvidersFailedError에는 여전히 잘리지 않은 전체 메시지가 담긴다.
_PRINT_TRUNCATE_LIMIT = 300


def _truncate_for_print(text: str, limit: int = _PRINT_TRUNCATE_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... (총 {len(text)}자, 나머지는 생략)"


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
            error_text = str(e)
            print(
                yellow(
                    f"[fallback] {name} 실패, 다음 provider로 전환: "
                    f"{_truncate_for_print(error_text)}"
                )
            )
            failures.append(f"{name}: {error_text}")

    raise AllProvidersFailedError(
        "모든 provider가 실패했습니다.\n" + "\n".join(failures)
    )


if __name__ == "__main__":
    result = call_llm("한 문장으로 너를 소개해줘.")
    print(result)
