import os

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/v1/chat/completions"
DEFAULT_MODEL = "qwen3.5:9b"


class OllamaError(Exception):
    pass


# Ollama가 모델을 메모리에서 내렸다가(idle timeout) 다시 로드하면 생성 시작 전에만
# 2분 넘게 걸릴 수 있다 (실측: 9.7B Q4 모델 콜드 리로드 약 150초). 원격 provider보다
# timeout을 훨씬 크게 잡아야 콜드 스타트에서 바로 실패로 처리되지 않는다.
def call_ollama(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 300) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        # Qwen3.5 같은 hybrid-thinking 모델이 <think>...</think> 추론 블록을 content에
        # 그대로 섞어 반환해서 JSON 파싱이 깨진다. think=false로 끄면 추론은 별도
        # reasoning 필드로 빠지고 content는 최종 답변만 깔끔하게 남는다.
        "think": False,
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        raise OllamaError(f"Ollama 요청이 {timeout}초 내에 응답하지 않았습니다.")
    except requests.exceptions.ConnectionError:
        raise OllamaError(
            f"Ollama({OLLAMA_BASE_URL})에 연결할 수 없습니다. Ollama가 실행 중인지 확인하세요."
        )
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Ollama 요청 중 알 수 없는 오류가 발생했습니다: {e}")

    if response.status_code == 404:
        raise OllamaError(
            f"Ollama에 '{model}' 모델이 없습니다 (404). 'ollama pull {model}'로 받아야 합니다."
        )
    if response.status_code >= 500:
        raise OllamaError(f"Ollama 서버 오류입니다 ({response.status_code}).")
    if response.status_code != 200:
        raise OllamaError(
            f"Ollama API가 예상치 못한 상태 코드를 반환했습니다: "
            f"{response.status_code} - {response.text}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise OllamaError(f"Ollama 응답 형식이 예상과 다릅니다: {e} / raw={response.text}")

    if not content:
        raise OllamaError(f"Ollama 응답에 content가 비어 있습니다: raw={response.text}")
    return content


if __name__ == "__main__":
    result = call_ollama("한 문장으로 너를 소개해줘.")
    print(result)
