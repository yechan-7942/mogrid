from tools.exec_tools import check_process, run_command, start_process, stop_process
from tools.file_tools import (
    ToolError,
    append_file,
    list_files,
    make_dir,
    read_file,
    search_files,
    write_file,
)

TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": (
            "디렉터리 안의 파일/폴더 목록을 반환한다. 경로를 모를 때 먼저 사용한다. "
            "모든 파일 tool(list_files/search_files/read_file/write_file/append_file/make_dir)은 "
            "프로젝트 폴더 밖의 경로에는 접근할 수 없다."
        ),
        "args": {"path": "확인할 디렉터리 경로 (기본값 '.')"},
    },
    {
        "name": "search_files",
        "description": "지정한 경로 하위를 재귀적으로 뒤져서 파일 이름이나 내용에 keyword가 포함된 파일을 찾는다. 여러 폴더에 걸쳐 파일을 찾아야 할 때 사용한다.",
        "args": {"keyword": "찾을 파일 이름/내용 키워드", "path": "검색을 시작할 디렉터리 경로 (기본값 '.')"},
    },
    {
        "name": "read_file",
        "description": "파일 내용을 읽어서 문자열로 반환한다.",
        "args": {"path": "읽을 파일 경로"},
    },
    {
        "name": "write_file",
        "description": "문자열 내용을 파일에 저장한다. 파일이 없으면 새로 만들고, 있으면 덮어쓴다.",
        "args": {"path": "저장할 파일 경로", "content": "파일에 쓸 내용"},
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
        "name": "run_command",
        "description": (
            "허용된 명령어(npm, npx, node, yarn, pip, pip3, python, python3, pytest, git, curl, "
            "docker, docker-compose)만 실행하고, 끝날 때까지 기다렸다가 결과를 반환한다. 패키지 "
            "설치, 빌드, 테스트 실행, git 조작, curl로 응답 확인, docker build/push 등 '끝나는' "
            "명령에 사용한다. 서버처럼 계속 떠 있어야 "
            "하는 명령에 쓰면 타임아웃으로 항상 실패하니 start_process를 대신 사용해라. "
            "프로젝트 폴더 밖에서는 실행할 수 없고, 허용 목록에 없는 명령어는 실패로 반환된다."
        ),
        "args": {
            "command": "실행할 명령어 전체 (예: 'npm install express')",
            "cwd": "명령을 실행할 디렉터리 (기본값 '.', 프로젝트 폴더 기준)",
        },
    },
    {
        "name": "start_process",
        "description": (
            "명령을 백그라운드로 실행하고 즉시 process_id를 반환한다 (기다리지 않음). "
            "서버, watch 모드처럼 계속 떠 있어야 하는 명령에 사용한다. 허용 명령어/프로젝트 "
            "폴더 제한은 run_command와 동일하다. 실행 직후 바로 죽으면(포트 충돌, 문법 오류 "
            "등) 그 사실과 출력을 바로 반환한다."
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
        "description": "start_process로 띄운 프로세스를 종료한다. 확인이 끝난 백그라운드 프로세스는 반드시 이걸로 정리해라.",
        "args": {"process_id": "start_process가 반환한 process_id"},
    },
]

TOOLS = {
    "list_files": list_files,
    "search_files": search_files,
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "make_dir": make_dir,
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
