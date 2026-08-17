import os
import shlex
import subprocess

from tools.file_tools import ToolError

PROJECT_ROOT_ENV = "MOGRID_PROJECT_ROOT"
ALLOWED_COMMANDS = {
    "npm", "npx", "node", "yarn",
    "pip", "pip3", "python", "python3", "pytest",
    "git",
}
COMMAND_TIMEOUT = 60
MAX_OUTPUT_CHARS = 3000


def _project_root() -> str:
    root = os.environ.get(PROJECT_ROOT_ENV) or os.getcwd()
    return os.path.realpath(root)


def _resolve_cwd(cwd: str) -> str:
    project_root = _project_root()
    target = os.path.realpath(os.path.join(project_root, cwd))
    outside = True
    try:
        outside = os.path.commonpath([target, project_root]) != project_root
    except ValueError:
        outside = True
    if outside:
        raise ToolError(
            f"프로젝트 폴더({project_root}) 밖의 경로에서는 명령을 실행할 수 없습니다: {cwd}"
        )
    if not os.path.isdir(target):
        raise ToolError(f"작업 디렉터리를 찾을 수 없습니다: {cwd}")
    return target


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n...(출력이 길어 생략됨)"


def run_command(command: str, cwd: str = ".") -> str:
    if not command or not command.strip():
        raise ToolError("실행할 명령어가 비어 있습니다.")

    try:
        parts = shlex.split(command)
    except ValueError as e:
        raise ToolError(f"명령어를 파싱할 수 없습니다: {command} ({e})")
    if not parts:
        raise ToolError("실행할 명령어가 비어 있습니다.")

    program = parts[0]
    if program not in ALLOWED_COMMANDS:
        raise ToolError(
            f"허용되지 않은 명령어입니다: {program} "
            f"(허용 목록: {', '.join(sorted(ALLOWED_COMMANDS))})"
        )

    resolved_cwd = _resolve_cwd(cwd)

    try:
        # shell=False: parts는 shlex로 이미 토큰화됐으므로 셸이 다시 해석하지 않는다.
        # shell=True를 쓰면 program이 allowlist를 통과해도 ";"/"&&"/백틱으로 뒤에
        # 임의 명령을 이어붙일 수 있어 allowlist가 무력화된다.
        result = subprocess.run(
            parts,
            cwd=resolved_cwd,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            shell=False,
        )
    except FileNotFoundError:
        raise ToolError(f"명령어를 찾을 수 없습니다 (설치되어 있는지 확인하세요): {program}")
    except subprocess.TimeoutExpired:
        raise ToolError(f"명령어가 {COMMAND_TIMEOUT}초 내에 끝나지 않았습니다: {command}")

    output = f"(exit code: {result.returncode})\n"
    if result.stdout:
        output += f"--- stdout ---\n{_truncate(result.stdout)}\n"
    if result.stderr:
        output += f"--- stderr ---\n{_truncate(result.stderr)}\n"
    return output
