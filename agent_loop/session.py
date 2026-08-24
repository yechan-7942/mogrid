import json
import os

from agent_loop.text_utils import cap_entries
from tools.sandbox import project_root

# 세션 파일은 어느 프로젝트를 작업 중인지(MOGRID_PROJECT_ROOT/cwd)별로 따로 저장해야 한다.
# 예전에는 이 경로가 mogrid 저장소 자체에 고정돼 있어서, 서로 다른 프로젝트에서 작업해도
# 세션 기록이 하나로 섞였다 (프로젝트 A에서 하던 작업 지시가 프로젝트 B의 새 작업에
# 끼어드는 문제로 실제 발생). 대신 project_root()별로 파일을 나누되, 그 프로젝트 폴더
# 안에 흔적을 남기지 않도록(각 대상 저장소의 .gitignore를 건드리지 않도록) mogrid 전용
# 홈 디렉터리에 경로를 인코딩한 파일명으로 저장한다.
SESSION_DIR = os.path.expanduser("~/.mogrid/sessions")

# 매 스텝 프롬프트에 세션 전체가 그대로 삽입되므로, 무한정 쌓이면 토큰 한도/rate limit에
# 걸릴 수 있다. 개수와 항목당 길이를 둘 다 제한해 상한선을 둔다.
MAX_SESSION_ENTRIES = 10
MAX_ENTRY_CHARS = 2000


class SessionError(Exception):
    pass


def trim_session(entries: list[str]) -> list[str]:
    return cap_entries(entries, MAX_SESSION_ENTRIES, MAX_ENTRY_CHARS)


def session_file_path() -> str:
    safe_name = project_root().strip(os.sep).replace(os.sep, "-") or "root"
    return os.path.join(SESSION_DIR, f"{safe_name}.json")


def load_session(path: str | None = None) -> list[str]:
    path = path or session_file_path()
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


def save_session(entries: list[str], path: str | None = None) -> None:
    make_parent = path is None
    path = path or session_file_path()
    try:
        if make_parent:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trim_session(entries), f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise SessionError(f"세션 파일을 저장하는 중 오류가 발생했습니다: {path} ({e})")
