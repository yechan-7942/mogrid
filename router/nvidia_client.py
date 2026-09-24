import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"

# DEFAULT_MODEL이 과부하/한도초과로 실패해도, NVIDIA build는 같은 API 키로 여러 모델을
# 무료 제공하니 provider 자체를 포기하기 전에 이 목록을 순서대로 소진한다.
#
# 여기 있는 모델은 전부 "실제로 호출해서 응답을 받아본" 것만 남긴다. /models 목록에
# 있다는 건 호출 가능하다는 뜻이 아니다 — 목록에 멀쩡히 뜨는데 호출하면 즉시 404를
# 내는 모델이 절반이 넘는다(llama-3.1-nemotron-ultra-253b-v1, mistral-large-2-instruct,
# nemotron-nano-3-30b-a3b, nemotron-4-340b-instruct, mixtral-8x22b, dbrx-instruct,
# yi-large 등이 전부 그랬다). 그래서 `mogrid check-models`의 OK만 믿고 여기 추가하지
# 말고, 반드시 아래처럼 한 번 호출해보고 넣어라:
#   python3 -c "from router.nvidia_client import _call_nvidia_model; import os; \
#     from dotenv import load_dotenv; load_dotenv(); \
#     print(_call_nvidia_model('1+1?', '<모델>', 30, os.getenv('NVIDIA_API_KEY')))"
# (짧은 시간에 여러 모델을 병렬로 두드리면 503/401로 막히니 순차로 확인할 것.)
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "z-ai/glm-5.3",
    "nvidia/nemotron-3-super-120b-a12b",
    "meta/muse-glimmer-30b",
    "z-ai/glm-5.3-flash",
]

# requests의 timeout은 "소켓 연산 하나"에 걸리는 값이라 총 소요시간을 보장하지 않는다.
# 실제로 timeout=40을 준 호출이 991초를 매달린 적이 있다(연결은 살아 있는데 응답이
# 계속 안 끝나는 경우). 모델을 여러 개 순회하는 구조에서는 이게 그대로 곱해지므로,
# (연결, 읽기) 튜플로 각각 조이고 루프 전체에도 별도 예산을 둔다.
CONNECT_TIMEOUT = 10
TOTAL_BUDGET_MULTIPLIER = 2.5


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
        response = requests.post(
            NVIDIA_API_URL,
            headers=headers,
            json=payload,
            timeout=(CONNECT_TIMEOUT, timeout),
        )
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

    # 모델 하나가 timeout을 꽉 채워도 나머지를 계속 도는 걸 막는다. 이게 없으면
    # 느린 모델이 몇 개 걸릴 때 한 스텝이 수 분~수십 분 멈춰서, 폴백이 오히려
    # 응답을 못 받게 만드는 역효과가 난다.
    budget = timeout * TOTAL_BUDGET_MULTIPLIER
    started = time.monotonic()

    failures = []
    for candidate in FALLBACK_MODELS:
        elapsed = time.monotonic() - started
        if elapsed >= budget:
            failures.append(
                f"남은 모델({', '.join(FALLBACK_MODELS[len(failures):])})은 "
                f"전체 예산 {budget:.0f}초를 넘겨 시도하지 않았습니다."
            )
            break
        # 남은 예산보다 긴 timeout을 주면 예산이 의미가 없어지므로 잘라서 넘긴다.
        remaining = max(1, int(budget - elapsed))
        try:
            return _call_nvidia_model(prompt, candidate, min(timeout, remaining), api_key)
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
