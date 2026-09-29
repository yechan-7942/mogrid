from tools.exec_tools import check_process, run_command, start_process, stop_process
from tools.file_tools import (
    ToolError,
    append_file,
    edit_file,
    list_files,
    make_dir,
    read_file,
    search_files,
    write_file,
)
from tools.skills import load_skill
from tools.task_tracker import update_task_list

TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": (
            "디렉터리 안의 파일/폴더 목록을 반환한다. "
            "모든 파일 tool은 프로젝트 폴더 밖의 경로에 접근할 수 없다."
        ),
        "args": {"path": "확인할 디렉터리 경로 (기본값 '.')"},
    },
    {
        "name": "search_files",
        "description": (
            "경로 하위를 재귀적으로 뒤져 파일 이름이나 내용에 keyword가 포함된 파일을 찾는다. "
            "한 파일에서 일치하는 줄을 최대 5줄까지 보여준다."
        ),
        "args": {
            "keyword": "찾을 파일 이름/내용 키워드 (regex=true면 정규식)",
            "path": "검색을 시작할 디렉터리 경로 (기본값 '.')",
            "regex": "keyword를 정규식으로 해석할지 여부 (기본값 false)",
        },
    },
    {
        "name": "read_file",
        "description": "파일 내용을 문자열로 반환한다. offset/limit이 없으면 전체를 반환한다.",
        "args": {
            "path": "읽을 파일 경로",
            "offset": "읽기 시작할 줄 번호, 1부터 시작 (기본값 1)",
            "limit": "몇 줄을 읽을지 (기본값: 끝까지 전부)",
        },
    },
    {
        "name": "write_file",
        "description": "문자열 내용을 파일에 저장한다. 파일이 없으면 새로 만들고, 있으면 덮어쓴다.",
        "args": {"path": "저장할 파일 경로", "content": "파일에 쓸 내용"},
    },
    {
        "name": "edit_file",
        "description": (
            "파일 안의 old_string을 new_string으로 바꾼다. old_string은 정확히 일치해야 하고 "
            "정확히 1번만 등장해야 한다 — 여러 번 등장하면 에러이므로 앞뒤 줄을 더 포함해 "
            "위치를 특정하거나, 전부 바꾸려면 replace_all=true를 줘라."
        ),
        "args": {
            "path": "수정할 파일 경로",
            "old_string": "바꿀 대상 문자열 (파일 내용과 정확히 일치해야 함)",
            "new_string": "바꿔넣을 문자열",
            "replace_all": "old_string의 모든 등장을 다 바꿀지 여부 (기본값 false)",
        },
    },
    {
        "name": "append_file",
        "description": "기존 파일 내용을 유지한 채로 문자열을 파일 끝에 추가한다.",
        "args": {"path": "이어쓸 파일 경로", "content": "파일 끝에 추가할 내용"},
    },
    {
        "name": "make_dir",
        "description": "디렉터리를 생성한다. 이미 존재해도 에러 없이 넘어간다.",
        "args": {"path": "생성할 디렉터리 경로"},
    },
    {
        "name": "update_task_list",
        "description": (
            "하위 작업 목록과 각각의 진행 상태를 기록한다. 호출할 때마다 현재 전체 목록을 "
            "통째로 다시 제출해라 (일부만 추가/수정하는 게 아니다)."
        ),
        "args": {
            "tasks": (
                '[{"content": "하위 작업 설명", "status": "pending|in_progress|completed"}, ...] '
                "형태의 리스트"
            ),
        },
    },
    {
        "name": "load_skill",
        "description": (
            "'사용 가능한 스킬' 목록에 있는 스킬의 전체 내용을 불러온다. 스킬은 이 프로젝트에서 "
            "그 작업을 할 때 따라야 할 절차가 적힌 문서다. 목록에 없는 이름은 부를 수 없다."
        ),
        "args": {"name": "불러올 스킬 이름 (목록에 적힌 그대로)"},
    },
    {
        "name": "run_command",
        "description": (
            "명령을 끝날 때까지 기다렸다가 결과를 반환한다. 허용 명령어(npm, npx, node, yarn, "
            "pip, pip3, python, python3, pytest, uv, git, curl, docker, docker-compose)만 "
            "실행되고, 프로젝트 폴더 밖에서는 실행할 수 없다."
        ),
        "args": {
            "command": "실행할 명령어 전체 (예: 'npm install express')",
            "cwd": "명령을 실행할 디렉터리 (기본값 '.', 프로젝트 폴더 기준)",
        },
    },
    {
        "name": "start_process",
        "description": (
            "명령을 백그라운드로 실행하고 기다리지 않고 즉시 process_id를 반환한다. 제한은 "
            "run_command와 같다. 실행 직후 죽으면(포트 충돌, 문법 오류 등) 그 사실과 출력을 반환한다."
        ),
        "args": {
            "command": "백그라운드로 실행할 명령어 (예: 'npm start')",
            "cwd": "명령을 실행할 디렉터리 (기본값 '.', 프로젝트 폴더 기준)",
        },
    },
    {
        "name": "check_process",
        "description": "start_process로 띄운 프로세스가 아직 실행 중인지와 지금까지의 출력을 확인한다.",
        "args": {"process_id": "start_process가 반환한 process_id"},
    },
    {
        "name": "stop_process",
        "description": "start_process로 띄운 프로세스를 종료한다.",
        "args": {"process_id": "start_process가 반환한 process_id"},
    },
]

TOOLS = {
    "list_files": list_files,
    "search_files": search_files,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "append_file": append_file,
    "make_dir": make_dir,
    "update_task_list": update_task_list,
    "load_skill": load_skill,
    "run_command": run_command,
    "start_process": start_process,
    "check_process": check_process,
    "stop_process": stop_process,
}


def call_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        raise ToolError(f"알 수 없는 tool입니다: {name}")
    try:
        return TOOLS[name](**args)
    except TypeError as e:
        raise ToolError(f"{name} 호출 인자가 잘못되었습니다: {e}")
