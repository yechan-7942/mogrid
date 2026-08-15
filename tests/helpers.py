import json


class FakeResponse:
    """requests.Response 흉내: status_code/json()/text만 있으면 되는 provider 클라이언트 테스트용."""

    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text else (json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON payload")
        return self._payload
