import os


class ToolError(Exception):
    pass


def list_files(path: str = ".") -> str:
    try:
        entries = os.listdir(path)
    except FileNotFoundError:
        raise ToolError(f"경로를 찾을 수 없습니다: {path}")
    except NotADirectoryError:
        raise ToolError(f"경로가 디렉터리가 아닙니다: {path}")
    except OSError as e:
        raise ToolError(f"디렉터리를 읽는 중 오류가 발생했습니다: {path} ({e})")
    return "\n".join(sorted(entries)) if entries else "(빈 디렉터리)"


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise ToolError(f"파일을 찾을 수 없습니다: {path}")
    except IsADirectoryError:
        raise ToolError(f"경로가 파일이 아니라 디렉터리입니다: {path}")
    except UnicodeDecodeError:
        raise ToolError(f"파일을 UTF-8로 읽을 수 없습니다 (바이너리 파일일 수 있음): {path}")
    except OSError as e:
        raise ToolError(f"파일을 읽는 중 오류가 발생했습니다: {path} ({e})")


def write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        raise ToolError(f"파일을 쓰는 중 오류가 발생했습니다: {path} ({e})")
    return f"{path}에 {len(content)}자 저장 완료"
