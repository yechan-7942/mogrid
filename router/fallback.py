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


def call_llm(prompt: str) -> str:
    failures = []

    for name, call_fn, error_cls in PROVIDERS:
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
