from router.codex_client import CodexError, call_codex
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
    # codex는 체인 중간에 둔다. 앞의 넷(무료 API)보다는 아껴 써야 하지만 — 유일하게
    # 무료 티어가 아니라 ChatGPT의 에이전트 할당량을 깎는다 — 뒤의 둘보다는 먼저
    # 닿는 게 낫다: nvidia는 목록에 있는 모델이 404를 내는 일이 잦고, ollama는 콜드
    # 스타트에 2~3분이 걸린다. 설치/로그인이 안 돼 있으면 CodexError로 즉시 빠지므로,
    # 안 쓰는 사람에게는 없는 것과 같다.
    ("codex", call_codex, CodexError),
    ("nvidia", call_nvidia, NvidiaError),
    ("ollama", call_ollama, OllamaError),
]


class AllProvidersFailedError(Exception):
    pass


# 매 호출마다 시작 provider를 한 칸씩 돌려서, 맨 앞(groq)으로 부하가 쏠려 그 provider만
# 레이트리밋에 먼저 도달하는 걸 막는다. 실패 시에는 여전히 나머지 provider를 순서대로
# 전부 시도한다 — 시작점만 바뀔 뿐 폴백 커버리지는 그대로.
_rotation = 0

# 로테이션은 "무료 자원끼리 부하를 나누는" 장치다. codex는 유일하게 무료 티어가 아니라
# 사용자의 ChatGPT 할당량을 깎으므로, 시작점으로는 뽑지 않는다 — 안 그러면 앞의 무료
# provider들이 멀쩡한데도 7번에 한 번은 유료 자원을 먼저 쓰게 된다. 체인에서 빼는 게
# 아니라 시작점 후보에서만 빼는 것이라, 앞의 provider들이 실패하면 여전히 codex로 넘어간다.
ROTATION_EXCLUDED = {"codex"}


def _reset_rotation() -> None:
    global _rotation
    _rotation = 0


def _rotation_start_indices() -> list[int]:
    indices = [i for i, (name, _, _) in enumerate(PROVIDERS) if name not in ROTATION_EXCLUDED]
    # 전부 제외되는 구성(테스트 등)에서는 로테이션을 끄지 말고 원래대로 전체를 쓴다.
    return indices or list(range(len(PROVIDERS)))


def call_llm(prompt: str) -> str:
    global _rotation
    failures = []
    candidates = _rotation_start_indices()
    start = candidates[_rotation % len(candidates)]
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
