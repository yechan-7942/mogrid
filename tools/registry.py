from tools.file_tools import ToolError, list_files, read_file, write_file

TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": "디렉터리 안의 파일/폴더 목록을 반환한다. 경로를 모를 때 먼저 사용한다.",
        "args": {"path": "확인할 디렉터리 경로 (기본값 '.')"},
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
]

TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
}


def call_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        raise ToolError(f"알 수 없는 tool입니다: {name}")
    try:
        return TOOLS[name](**args)
    except TypeError as e:
        raise ToolError(f"{name} 호출 인자가 잘못되었습니다: {e}")
