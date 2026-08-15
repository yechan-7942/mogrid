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
        "description": "디렉터리 안의 파일/폴더 목록을 반환한다. 경로를 모를 때 먼저 사용한다.",
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
]

TOOLS = {
    "list_files": list_files,
    "search_files": search_files,
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "make_dir": make_dir,
}


def call_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        raise ToolError(f"알 수 없는 tool입니다: {name}")
    try:
        return TOOLS[name](**args)
    except TypeError as e:
        raise ToolError(f"{name} 호출 인자가 잘못되었습니다: {e}")
