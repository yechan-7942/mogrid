import json
import os

SESSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".mogrid_session.json"
)

# 매 스텝 프롬프트에 세션 전체가 그대로 삽입되므로, 무한정 쌓이면 토큰 한도/rate limit에
# 걸릴 수 있다. 개수와 항목당 길이를 둘 다 제한해 상한선을 둔다.
MAX_SESSION_ENTRIES = 10
MAX_ENTRY_CHARS = 2000


class SessionError(Exception):
    pass


def trim_session(entries: list[str]) -> list[str]:
    capped = [
        entry if len(entry) <= MAX_ENTRY_CHARS else entry[:MAX_ENTRY_CHARS] + " …(생략됨)"
        for entry in entries
    ]
    return capped[-MAX_SESSION_ENTRIES:]


def load_session(path: str = SESSION_FILE) -> list[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise SessionError(f"세션 파일을 읽는 중 오류가 발생했습니다: {path} ({e})")
    except json.JSONDecodeError as e:
        raise SessionError(f"세션 파일이 손상되었습니다: {path} ({e})")
    if not isinstance(data, list):
        raise SessionError(f"세션 파일 형식이 올바르지 않습니다 (list가 아님): {path}")
    return trim_session(data)


def save_session(entries: list[str], path: str = SESSION_FILE) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trim_session(entries), f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise SessionError(f"세션 파일을 저장하는 중 오류가 발생했습니다: {path} ({e})")
