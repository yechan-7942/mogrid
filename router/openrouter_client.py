import os

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"


class OpenRouterError(Exception):
    pass


def call_openrouter(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 30) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY가 .env에 설정되어 있지 않습니다.")

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
            OPENROUTER_API_URL, headers=headers, json=payload, timeout=timeout
        )
    except requests.exceptions.Timeout:
        raise OpenRouterError(f"OpenRouter 요청이 {timeout}초 내에 응답하지 않았습니다.")
    except requests.exceptions.ConnectionError:
        raise OpenRouterError("OpenRouter API에 연결할 수 없습니다. 네트워크 상태를 확인하세요.")
    except requests.exceptions.RequestException as e:
        raise OpenRouterError(f"OpenRouter 요청 중 알 수 없는 오류가 발생했습니다: {e}")

    if response.status_code == 401:
        raise OpenRouterError("OPENROUTER_API_KEY가 유효하지 않습니다 (401 Unauthorized).")
    if response.status_code == 429:
        raise OpenRouterError("OpenRouter API 요청 한도를 초과했습니다 (429 Too Many Requests).")
    if response.status_code >= 500:
        raise OpenRouterError(f"OpenRouter 서버 오류입니다 ({response.status_code}).")
    if response.status_code != 200:
        raise OpenRouterError(
            f"OpenRouter API가 예상치 못한 상태 코드를 반환했습니다: "
            f"{response.status_code} - {response.text}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise OpenRouterError(f"OpenRouter 응답 형식이 예상과 다릅니다: {e} / raw={response.text}")

    if not content:
        raise OpenRouterError(
            f"OpenRouter 응답에 content가 비어 있습니다 (모델이 reasoning만 반환하고 "
            f"실제 답변은 생성하지 않았을 수 있음): raw={response.text}"
        )
    return content


if __name__ == "__main__":
    result = call_openrouter("한 문장으로 너를 소개해줘.")
    print(result)
