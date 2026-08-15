import json
import os

SESSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".mogrid_session.json"
)


class SessionError(Exception):
    pass


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
    return data


def save_session(entries: list[str], path: str = SESSION_FILE) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise SessionError(f"세션 파일을 저장하는 중 오류가 발생했습니다: {path} ({e})")
