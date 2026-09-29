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

# 세션이 무한정 쌓이지 않도록 개수와 항목당 길이를 둘 다 제한한다. 이 상한은 "디스크에
# 남기는 원본"의 상한이다 — 프롬프트에 싣는 상한(아래)과 일부러 분리해 두었다.
MAX_SESSION_ENTRIES = 10
MAX_ENTRY_CHARS = 2000

# 프롬프트는 매 스텝 통째로 재전송되므로 세션 기록도 그대로 스텝당 반복 비용이 된다.
# 그렇다고 위의 저장 상한을 같이 낮추면 (1) 이미 저장돼 있던 기록이 다음 저장 때 잘려
# 영구히 사라지고 (2) summarizer가 요약할 원본까지 미리 깎여서 요약 품질이 떨어진다.
# 그래서 저장 상한은 그대로 두고, 프롬프트에 실을 때만 더 강하게 줄인다.
# 세션 기록은 "이전에 완료한 작업들"이라 이번 작업의 히스토리보다 덜 중요하고, 모델이
# 실제로 참조하는 건 방금 끝낸 한두 개다(예: "아까 만든 파일에 ~를 더해줘"). 그래서
# 히스토리와 같은 테이퍼링을 쓰되(cap_entries의 older_max_chars/recent_count) 상한 자체는
# 더 낮게 잡는다. 오래된 항목은 "무슨 작업을 했는지"만 남으면 충분하다.
PROMPT_RECENT_ENTRIES = 2
PROMPT_MAX_ENTRY_CHARS = 1000
PROMPT_OLDER_ENTRY_CHARS = 400


class SessionError(Exception):
    pass


def trim_session(entries: list[str]) -> list[str]:
    """디스크에 저장할(그리고 요약 원본으로 쓸) 형태로 자른다."""
    return cap_entries(entries, MAX_SESSION_ENTRIES, MAX_ENTRY_CHARS)


def session_prompt_entries(entries: list[str]) -> list[str]:
    """프롬프트에 실을 형태로 자른다. 저장본보다 더 강하게 줄인 사본을 돌려준다."""
    return cap_entries(
        entries,
        MAX_SESSION_ENTRIES,
        PROMPT_MAX_ENTRY_CHARS,
        PROMPT_OLDER_ENTRY_CHARS,
        PROMPT_RECENT_ENTRIES,
    )


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
