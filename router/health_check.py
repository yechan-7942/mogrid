import os

import requests
from dotenv import load_dotenv

from router.gemini_client import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from router.groq_client import DEFAULT_MODEL as GROQ_DEFAULT_MODEL
from router.mistral_client import DEFAULT_MODEL as MISTRAL_DEFAULT_MODEL
from router.nvidia_client import DEFAULT_MODEL as NVIDIA_DEFAULT_MODEL
from router.nvidia_client import FALLBACK_MODELS as NVIDIA_FALLBACK_MODELS
from router.ollama_client import DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL
from router.ollama_client import OLLAMA_BASE_URL
from router.openrouter_client import DEFAULT_MODEL as OPENROUTER_DEFAULT_MODEL

load_dotenv()

# status: "ok"(목록에 있음) / "missing"(provider는 응답했지만 목록에 없음) /
# "skipped"(키가 없거나 로컬 서버에 연결 불가) / "error"(조회 자체가 실패)
CheckResult = tuple[str, str, str]


def _check_openai_style_models(
    provider: str, api_key_env: str, models_url: str, default_model: str, timeout: int = 15
) -> CheckResult:
    """OpenAI 호환 {"data": [{"id": ...}, ...]} 형태의 /models 응답을 쓰는 provider 공용 체크."""
    api_key = os.getenv(api_key_env)
    if not api_key:
        return provider, "skipped", f"{api_key_env}가 설정되어 있지 않음"

    try:
        response = requests.get(
            models_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout
        )
    except requests.exceptions.RequestException as e:
        return provider, "error", f"모델 목록 조회 실패: {e}"

    if response.status_code != 200:
        return provider, "error", f"모델 목록 조회 실패 ({response.status_code}): {response.text}"

    try:
        model_ids = {m["id"] for m in response.json()["data"]}
    except (KeyError, ValueError, TypeError) as e:
        return provider, "error", f"응답 형식이 예상과 다름: {e}"

    if default_model in model_ids:
        return provider, "ok", f"{default_model} 사용 가능"
    return provider, "missing", f"{default_model}이 모델 목록에 없음 (교체가 필요할 수 있음)"


def check_groq() -> CheckResult:
    return _check_openai_style_models(
        "Groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1/models", GROQ_DEFAULT_MODEL
    )


def check_mistral() -> CheckResult:
    return _check_openai_style_models(
        "Mistral", "MISTRAL_API_KEY", "https://api.mistral.ai/v1/models", MISTRAL_DEFAULT_MODEL
    )


def check_nvidia() -> CheckResult:
    # DEFAULT_MODEL 하나만 보는 다른 provider와 달리, NVIDIA는 call_nvidia()가 내부적으로
    # FALLBACK_MODELS를 순서대로 시도하므로 그 목록 전체의 가용성을 같이 확인한다.
    # 폴백 모델 일부가 빠져도 DEFAULT_MODEL만 살아있으면 "ok"로 본다 — 그 나머지는
    # 보너스 자원이라 없어도 기능은 그대로 동작하기 때문.
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return "NVIDIA NIM", "skipped", "NVIDIA_API_KEY가 설정되어 있지 않음"

    try:
        response = requests.get(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        return "NVIDIA NIM", "error", f"모델 목록 조회 실패: {e}"
    if response.status_code != 200:
        return "NVIDIA NIM", "error", f"모델 목록 조회 실패 ({response.status_code}): {response.text}"
    try:
        model_ids = {m["id"] for m in response.json()["data"]}
    except (KeyError, ValueError, TypeError) as e:
        return "NVIDIA NIM", "error", f"응답 형식이 예상과 다름: {e}"

    if NVIDIA_DEFAULT_MODEL not in model_ids:
        return (
            "NVIDIA NIM",
            "missing",
            f"{NVIDIA_DEFAULT_MODEL}이 모델 목록에 없음 (교체가 필요할 수 있음)",
        )

    missing_fallbacks = [m for m in NVIDIA_FALLBACK_MODELS if m not in model_ids]
    if missing_fallbacks:
        return (
            "NVIDIA NIM",
            "ok",
            f"{NVIDIA_DEFAULT_MODEL} 사용 가능 (폴백 모델 중 {len(missing_fallbacks)}개 "
            f"목록에 없음: {', '.join(missing_fallbacks)})",
        )
    return (
        "NVIDIA NIM",
        "ok",
        f"{NVIDIA_DEFAULT_MODEL} 외 폴백 모델 {len(NVIDIA_FALLBACK_MODELS) - 1}개 모두 사용 가능",
    )


def check_openrouter() -> CheckResult:
    # OpenRouter 모델 카탈로그는 API 키 없이도 조회 가능하지만, 있으면 같이 보낸다.
    api_key = os.getenv("OPENROUTER_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        return "OpenRouter", "error", f"모델 목록 조회 실패: {e}"
    if response.status_code != 200:
        return "OpenRouter", "error", f"모델 목록 조회 실패 ({response.status_code}): {response.text}"
    try:
        model_ids = {m["id"] for m in response.json()["data"]}
    except (KeyError, ValueError, TypeError) as e:
        return "OpenRouter", "error", f"응답 형식이 예상과 다름: {e}"
    if OPENROUTER_DEFAULT_MODEL in model_ids:
        return "OpenRouter", "ok", f"{OPENROUTER_DEFAULT_MODEL} 사용 가능"
    return (
        "OpenRouter",
        "missing",
        f"{OPENROUTER_DEFAULT_MODEL}이 모델 목록에 없음 (무료 티어에서 빠졌을 수 있음)",
    )


def check_gemini() -> CheckResult:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini", "skipped", "GEMINI_API_KEY가 설정되어 있지 않음"
    try:
        response = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": api_key},
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        return "Gemini", "error", f"모델 목록 조회 실패: {e}"
    if response.status_code != 200:
        return "Gemini", "error", f"모델 목록 조회 실패 ({response.status_code}): {response.text}"
    try:
        model_names = {m["name"].removeprefix("models/") for m in response.json()["models"]}
    except (KeyError, ValueError, TypeError) as e:
        return "Gemini", "error", f"응답 형식이 예상과 다름: {e}"
    if GEMINI_DEFAULT_MODEL in model_names:
        return "Gemini", "ok", f"{GEMINI_DEFAULT_MODEL} 사용 가능"
    return "Gemini", "missing", f"{GEMINI_DEFAULT_MODEL}이 모델 목록에 없음 (교체가 필요할 수 있음)"


def check_ollama() -> CheckResult:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
    except requests.exceptions.RequestException:
        return "Ollama", "skipped", f"Ollama({OLLAMA_BASE_URL})에 연결할 수 없음 (실행 중인지 확인)"
    if response.status_code != 200:
        return "Ollama", "error", f"모델 목록 조회 실패 ({response.status_code}): {response.text}"
    try:
        model_names = {m["name"] for m in response.json()["models"]}
    except (KeyError, ValueError, TypeError) as e:
        return "Ollama", "error", f"응답 형식이 예상과 다름: {e}"
    if OLLAMA_DEFAULT_MODEL in model_names:
        return "Ollama", "ok", f"{OLLAMA_DEFAULT_MODEL} 사용 가능"
    return (
        "Ollama",
        "missing",
        f"{OLLAMA_DEFAULT_MODEL}이 로컬에 없음 (`ollama pull {OLLAMA_DEFAULT_MODEL}` 필요)",
    )


ALL_CHECKS = (check_groq, check_gemini, check_openrouter, check_mistral, check_nvidia, check_ollama)


def run_all_checks() -> list[CheckResult]:
    return [check() for check in ALL_CHECKS]
