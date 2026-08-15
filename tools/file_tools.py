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


def append_file(path: str, content: str) -> str:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        raise ToolError(f"파일에 이어쓰는 중 오류가 발생했습니다: {path} ({e})")
    return f"{path}에 {len(content)}자 추가 완료"


def make_dir(path: str) -> str:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise ToolError(f"디렉터리를 만드는 중 오류가 발생했습니다: {path} ({e})")
    return f"{path} 디렉터리 생성 완료"


_SEARCH_SKIP_DIRS = {"__pycache__", "venv", "node_modules"}
_SEARCH_MAX_MATCHES = 50


def search_files(keyword: str, path: str = ".") -> str:
    if not keyword:
        raise ToolError("검색어(keyword)가 비어 있습니다.")
    if not os.path.isdir(path):
        raise ToolError(f"경로가 디렉터리가 아니거나 존재하지 않습니다: {path}")

    matches = []
    truncated = False
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SEARCH_SKIP_DIRS and not d.startswith(".")]
        for name in sorted(files):
            if len(matches) >= _SEARCH_MAX_MATCHES:
                truncated = True
                break
            full_path = os.path.join(root, name)
            if keyword.lower() in name.lower():
                matches.append(f"{full_path} (파일명 일치)")
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    for lineno, line in enumerate(f, start=1):
                        if keyword in line:
                            matches.append(f"{full_path}:{lineno}: {line.strip()}")
                            break
            except (UnicodeDecodeError, OSError):
                continue
        if truncated:
            break

    if not matches:
        return f"'{keyword}'에 대한 검색 결과가 없습니다."
    result = "\n".join(matches)
    if truncated:
        result += f"\n(결과가 {_SEARCH_MAX_MATCHES}개를 넘어 일부만 표시됨)"
    return result
