import os

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-3.6-flash"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


class GeminiError(Exception):
    pass


def call_gemini(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 30) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY가 .env에 설정되어 있지 않습니다.")

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {"model": model, "input": prompt}

    try:
        response = requests.post(
            INTERACTIONS_URL, headers=headers, json=payload, timeout=timeout
        )
    except requests.exceptions.Timeout:
        raise GeminiError(f"Gemini 요청이 {timeout}초 내에 응답하지 않았습니다.")
    except requests.exceptions.ConnectionError:
        raise GeminiError("Gemini API에 연결할 수 없습니다. 네트워크 상태를 확인하세요.")
    except requests.exceptions.RequestException as e:
        raise GeminiError(f"Gemini 요청 중 알 수 없는 오류가 발생했습니다: {e}")

    if response.status_code == 400:
        raise GeminiError(f"Gemini 요청이 잘못되었습니다 (400 Bad Request): {response.text}")
    if response.status_code == 403:
        raise GeminiError("GEMINI_API_KEY가 유효하지 않거나 권한이 없습니다 (403 Forbidden).")
    if response.status_code == 429:
        raise GeminiError("Gemini API 요청 한도를 초과했습니다 (429 Too Many Requests).")
    if response.status_code >= 500:
        raise GeminiError(f"Gemini 서버 오류입니다 ({response.status_code}).")
    if response.status_code != 200:
        raise GeminiError(
            f"Gemini API가 예상치 못한 상태 코드를 반환했습니다: "
            f"{response.status_code} - {response.text}"
        )

    try:
        data = response.json()
        steps = data["steps"]
        model_outputs = [s for s in steps if s.get("type") == "model_output"]
        if not model_outputs:
            raise GeminiError(f"Gemini 응답에 model_output 스텝이 없습니다: raw={response.text}")
        last_output = model_outputs[-1]
        texts = [c["text"] for c in last_output["content"] if c.get("type") == "text"]
        if not texts:
            raise GeminiError(f"Gemini 응답에 텍스트 콘텐츠가 없습니다: raw={response.text}")
        return "".join(texts)
    except (KeyError, IndexError, ValueError) as e:
        raise GeminiError(f"Gemini 응답 형식이 예상과 다릅니다: {e} / raw={response.text}")


if __name__ == "__main__":
    result = call_gemini("한 문장으로 너를 소개해줘.")
    print(result)
