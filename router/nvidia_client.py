import os

import requests
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"

# DEFAULT_MODEL이 과부하/한도초과로 실패해도, NVIDIA build는 같은 API 키로 여러 모델을
# 무료 제공하니 provider 자체를 포기하기 전에 이 목록을 순서대로 소진한다.
# (대형/고품질 모델 -> 중소형 모델 순. 실제 가용 여부는 `mogrid check-models`로 확인)
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "nvidia/nemotron-3-super-120b-a12b",
    "openai/gpt-oss-20b",
    "mistralai/mistral-large-2-instruct",
    "nvidia/nemotron-nano-3-30b-a3b",
]


class NvidiaError(Exception):
    """모델 하나에 대한 실패. 다음 모델로 넘어가도 되는 경우 이 타입으로 raise한다."""


class NvidiaAccountError(NvidiaError):
    """API 키/네트워크처럼 계정 단위 문제. 모델을 바꿔도 결과가 같으므로 즉시 중단한다."""


def _call_nvidia_model(prompt: str, model: str, timeout: int, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        response = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        raise NvidiaError(f"NVIDIA NIM({model}) 요청이 {timeout}초 내에 응답하지 않았습니다.")
    except requests.exceptions.ConnectionError:
        raise NvidiaAccountError("NVIDIA NIM API에 연결할 수 없습니다. 네트워크 상태를 확인하세요.")
    except requests.exceptions.RequestException as e:
        raise NvidiaError(f"NVIDIA NIM({model}) 요청 중 알 수 없는 오류가 발생했습니다: {e}")

    if response.status_code == 401:
        raise NvidiaAccountError("NVIDIA_API_KEY가 유효하지 않습니다 (401 Unauthorized).")
    if response.status_code == 429:
        raise NvidiaError(
            f"NVIDIA NIM({model}) API 요청 한도를 초과했습니다 (429 Too Many Requests)."
        )
    if response.status_code >= 500:
        raise NvidiaError(f"NVIDIA NIM({model}) 서버 오류입니다 ({response.status_code}).")
    if response.status_code != 200:
        raise NvidiaError(
            f"NVIDIA NIM({model}) API가 예상치 못한 상태 코드를 반환했습니다: "
            f"{response.status_code} - {response.text}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise NvidiaError(f"NVIDIA NIM({model}) 응답 형식이 예상과 다릅니다: {e} / raw={response.text}")

    if not content:
        raise NvidiaError(
            f"NVIDIA NIM({model}) 응답에 content가 비어 있습니다 (모델이 reasoning만 반환하고 "
            f"실제 답변은 생성하지 않았을 수 있음): raw={response.text}"
        )
    return content


def call_nvidia(prompt: str, model: str | None = None, timeout: int = 60) -> str:
    """model을 명시하면 그 모델 하나만 호출한다. 생략하면 FALLBACK_MODELS를 순서대로
    시도하다가, 계정 단위 문제(NvidiaAccountError)를 만나면 즉시 멈추고, 그 외 모델별
    실패는 다음 모델로 넘어간다."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise NvidiaError("NVIDIA_API_KEY가 .env에 설정되어 있지 않습니다.")

    if model is not None:
        return _call_nvidia_model(prompt, model, timeout, api_key)

    failures = []
    for candidate in FALLBACK_MODELS:
        try:
            return _call_nvidia_model(prompt, candidate, timeout, api_key)
        except NvidiaAccountError:
            raise
        except NvidiaError as e:
            failures.append(str(e))

    raise NvidiaError(
        "NVIDIA NIM 모델을 순서대로 모두 시도했지만 전부 실패했습니다.\n" + "\n".join(failures)
    )


if __name__ == "__main__":
    result = call_nvidia("한 문장으로 너를 소개해줘.")
    print(result)
