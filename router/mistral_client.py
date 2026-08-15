import os

import requests
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MODEL = "mistral-small-latest"


class MistralError(Exception):
    pass


def call_mistral(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 30) -> str:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise MistralError("MISTRAL_API_KEY가 .env에 설정되어 있지 않습니다.")

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
            MISTRAL_API_URL, headers=headers, json=payload, timeout=timeout
        )
    except requests.exceptions.Timeout:
        raise MistralError(f"Mistral 요청이 {timeout}초 내에 응답하지 않았습니다.")
    except requests.exceptions.ConnectionError:
        raise MistralError("Mistral API에 연결할 수 없습니다. 네트워크 상태를 확인하세요.")
    except requests.exceptions.RequestException as e:
        raise MistralError(f"Mistral 요청 중 알 수 없는 오류가 발생했습니다: {e}")

    if response.status_code == 401:
        raise MistralError("MISTRAL_API_KEY가 유효하지 않습니다 (401 Unauthorized).")
    if response.status_code == 429:
        raise MistralError("Mistral API 요청 한도를 초과했습니다 (429 Too Many Requests).")
    if response.status_code >= 500:
        raise MistralError(f"Mistral 서버 오류입니다 ({response.status_code}).")
    if response.status_code != 200:
        raise MistralError(
            f"Mistral API가 예상치 못한 상태 코드를 반환했습니다: "
            f"{response.status_code} - {response.text}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise MistralError(f"Mistral 응답 형식이 예상과 다릅니다: {e} / raw={response.text}")

    if not content:
        raise MistralError(
            f"Mistral 응답에 content가 비어 있습니다: raw={response.text}"
        )
    return content


if __name__ == "__main__":
    result = call_mistral("한 문장으로 너를 소개해줘.")
    print(result)
