from tools.file_tools import ToolError

VALID_STATUSES = {"pending", "in_progress", "completed"}
_STATUS_ICON = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}

_tasks: list[dict] = []


def reset_tasks() -> None:
    global _tasks
    _tasks = []


def update_task_list(tasks: list) -> str:
    if not isinstance(tasks, list):
        raise ToolError("tasks는 리스트여야 합니다.")
    for t in tasks:
        if not isinstance(t, dict) or "content" not in t or "status" not in t:
            raise ToolError(
                "tasks의 각 항목은 content와 status를 가진 객체여야 합니다: "
                '{"content": "...", "status": "pending|in_progress|completed"}'
            )
        if t["status"] not in VALID_STATUSES:
            raise ToolError(
                f"status는 {sorted(VALID_STATUSES)} 중 하나여야 합니다: {t['status']}"
            )

    global _tasks
    _tasks = tasks
    return f"작업 목록 {len(tasks)}개로 갱신 완료"


def render_task_list() -> str:
    if not _tasks:
        return "(작업 목록 없음)"
    return "\n".join(f"{_STATUS_ICON[t['status']]} {t['content']}" for t in _tasks)
