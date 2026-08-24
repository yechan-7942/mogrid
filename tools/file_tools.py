import os
import re

from tools.sandbox import PathEscapesProjectRoot
from tools.sandbox import resolve_path as _sandbox_resolve_path


class ToolError(Exception):
    pass


def _resolve(path: str) -> str:
    try:
        return _sandbox_resolve_path(path)
    except PathEscapesProjectRoot as e:
        raise ToolError(str(e))


def list_files(path: str = ".") -> str:
    target = _resolve(path)
    try:
        entries = os.listdir(target)
    except FileNotFoundError:
        raise ToolError(f"경로를 찾을 수 없습니다: {path}")
    except NotADirectoryError:
        raise ToolError(f"경로가 디렉터리가 아닙니다: {path}")
    except OSError as e:
        raise ToolError(f"디렉터리를 읽는 중 오류가 발생했습니다: {path} ({e})")
    return "\n".join(sorted(entries)) if entries else "(빈 디렉터리)"


def read_file(path: str, offset: int = 1, limit: int | None = None) -> str:
    target = _resolve(path)
    try:
        with open(target, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        raise ToolError(f"파일을 찾을 수 없습니다: {path}")
    except IsADirectoryError:
        raise ToolError(f"경로가 파일이 아니라 디렉터리입니다: {path}")
    except UnicodeDecodeError:
        raise ToolError(f"파일을 UTF-8로 읽을 수 없습니다 (바이너리 파일일 수 있음): {path}")
    except OSError as e:
        raise ToolError(f"파일을 읽는 중 오류가 발생했습니다: {path} ({e})")

    if offset < 1:
        raise ToolError("offset은 1 이상이어야 합니다 (파일의 첫 줄이 1번줄).")
    if limit is not None and limit < 1:
        raise ToolError("limit은 1 이상이어야 합니다.")

    total = len(lines)
    start = offset - 1
    if total == 0:
        return ""
    if start >= total:
        raise ToolError(f"offset({offset})이 파일의 전체 줄 수({total})를 넘어섰습니다.")

    end = total if limit is None else min(start + limit, total)
    content = "".join(lines[start:end])
    if end < total:
        content += (
            f"\n(파일 전체 {total}줄 중 {offset}~{end}번째 줄만 표시됨. "
            "나머지를 읽으려면 offset을 늘려 다시 호출해라.)"
        )
    return content


def write_file(path: str, content: str) -> str:
    target = _resolve(path)
    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        raise ToolError(f"파일을 쓰는 중 오류가 발생했습니다: {path} ({e})")
    return f"{path}에 {len(content)}자 저장 완료"


def append_file(path: str, content: str) -> str:
    target = _resolve(path)
    try:
        with open(target, "a", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        raise ToolError(f"파일에 이어쓰는 중 오류가 발생했습니다: {path} ({e})")
    return f"{path}에 {len(content)}자 추가 완료"


def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    if old_string == new_string:
        raise ToolError("old_string과 new_string이 동일합니다. 변경 내용이 없습니다.")
    target = _resolve(path)
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        raise ToolError(f"파일을 찾을 수 없습니다: {path}")
    except IsADirectoryError:
        raise ToolError(f"경로가 파일이 아니라 디렉터리입니다: {path}")
    except UnicodeDecodeError:
        raise ToolError(f"파일을 UTF-8로 읽을 수 없습니다 (바이너리 파일일 수 있음): {path}")
    except OSError as e:
        raise ToolError(f"파일을 읽는 중 오류가 발생했습니다: {path} ({e})")

    count = content.count(old_string)
    if count == 0:
        raise ToolError(f"old_string을 파일에서 찾을 수 없습니다: {path}")
    if count > 1 and not replace_all:
        raise ToolError(
            f"old_string이 파일 안에 {count}번 등장합니다. 어느 곳을 바꿀지 특정할 수 "
            "있도록 old_string에 주변 맥락을 더 포함시키거나, 전부 바꾸려면 "
            "replace_all=true를 사용해라."
        )

    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(new_content)
    except OSError as e:
        raise ToolError(f"파일을 쓰는 중 오류가 발생했습니다: {path} ({e})")
    return f"{path}에서 {count}곳 교체 완료" if replace_all else f"{path}에서 1곳 교체 완료"


def make_dir(path: str) -> str:
    target = _resolve(path)
    try:
        os.makedirs(target, exist_ok=True)
    except OSError as e:
        raise ToolError(f"디렉터리를 만드는 중 오류가 발생했습니다: {path} ({e})")
    return f"{path} 디렉터리 생성 완료"


_SEARCH_SKIP_DIRS = {"__pycache__", "venv", "node_modules"}
_SEARCH_MAX_MATCHES = 50
_SEARCH_MAX_MATCHES_PER_FILE = 5


def search_files(keyword: str, path: str = ".", regex: bool = False) -> str:
    if not keyword:
        raise ToolError("검색어(keyword)가 비어 있습니다.")
    target = _resolve(path)
    if not os.path.isdir(target):
        raise ToolError(f"경로가 디렉터리가 아니거나 존재하지 않습니다: {path}")

    if regex:
        try:
            pattern = re.compile(keyword)
        except re.error as e:
            raise ToolError(f"정규식이 올바르지 않습니다: {keyword} ({e})")
        name_matches = lambda name: pattern.search(name) is not None
        line_matches = lambda line: pattern.search(line) is not None
    else:
        keyword_lower = keyword.lower()
        name_matches = lambda name: keyword_lower in name.lower()
        line_matches = lambda line: keyword in line

    matches = []
    truncated = False
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in _SEARCH_SKIP_DIRS and not d.startswith(".")]
        for name in sorted(files):
            if len(matches) >= _SEARCH_MAX_MATCHES:
                truncated = True
                break
            full_path = os.path.join(root, name)
            if name_matches(name):
                matches.append(f"{full_path} (파일명 일치)")
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    file_match_count = 0
                    for lineno, line in enumerate(f, start=1):
                        if len(matches) >= _SEARCH_MAX_MATCHES:
                            truncated = True
                            break
                        if line_matches(line):
                            matches.append(f"{full_path}:{lineno}: {line.strip()}")
                            file_match_count += 1
                            if file_match_count >= _SEARCH_MAX_MATCHES_PER_FILE:
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
