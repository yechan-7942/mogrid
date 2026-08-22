import os
import shlex
import subprocess
import tempfile
import time
import uuid

from tools.file_tools import ToolError
from tools.sandbox import PROJECT_ROOT_ENV, PathEscapesProjectRoot
from tools.sandbox import resolve_path as _sandbox_resolve_path

ALLOWED_COMMANDS = {
    "npm", "npx", "node", "yarn",
    "pip", "pip3", "python", "python3", "pytest",
    "uv",
    "git", "curl",
    "docker", "docker-compose",
}
COMMAND_TIMEOUT = 60
MAX_OUTPUT_CHARS = 3000
STARTUP_GRACE_SECONDS = 1.0
PROCESS_STOP_TIMEOUT = 5

# start_process로 띄운 뒤 아직 정리되지 않은 프로세스: process_id -> {"popen", "log_path", "command"}
_PROCESSES: dict[str, dict] = {}


def _resolve_cwd(cwd: str) -> str:
    try:
        target = _sandbox_resolve_path(cwd)
    except PathEscapesProjectRoot as e:
        raise ToolError(f"프로젝트 폴더 밖의 경로에서는 명령을 실행할 수 없습니다: {e}")
    if not os.path.isdir(target):
        raise ToolError(f"작업 디렉터리를 찾을 수 없습니다: {cwd}")
    return target


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n...(출력이 길어 생략됨)"


def _parse_command(command: str) -> list[str]:
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
    return parts


def run_command(command: str, cwd: str = ".") -> str:
    parts = _parse_command(command)
    program = parts[0]
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


def _read_log(process_id: str) -> str:
    entry = _PROCESSES.get(process_id)
    if entry is None:
        return "(로그 없음)"
    try:
        with open(entry["log_path"], "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return "(로그를 읽을 수 없음)"
    return _truncate(content) if content else "(출력 없음)"


def _cleanup_process(process_id: str) -> None:
    entry = _PROCESSES.pop(process_id, None)
    if entry is None:
        return
    try:
        os.unlink(entry["log_path"])
    except OSError:
        pass


def start_process(command: str, cwd: str = ".") -> str:
    parts = _parse_command(command)
    program = parts[0]
    resolved_cwd = _resolve_cwd(cwd)

    log_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log")
    log_path = log_file.name
    try:
        popen = subprocess.Popen(
            parts,
            cwd=resolved_cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    except FileNotFoundError:
        log_file.close()
        os.unlink(log_path)
        raise ToolError(f"명령어를 찾을 수 없습니다 (설치되어 있는지 확인하세요): {program}")
    finally:
        log_file.close()

    process_id = uuid.uuid4().hex[:8]
    _PROCESSES[process_id] = {"popen": popen, "log_path": log_path, "command": command}

    # 바로 죽는 프로세스(포트 충돌, 문법 오류 등)를 즉시 잡아내기 위해 잠깐 기다렸다가 확인한다.
    time.sleep(STARTUP_GRACE_SECONDS)
    exit_code = popen.poll()
    output = _read_log(process_id)
    if exit_code is not None:
        _cleanup_process(process_id)
        return (
            f"실행 후 바로 종료됨 (exit code: {exit_code})\n--- 출력 ---\n{output}"
        )
    return f"process_id={process_id} 로 백그라운드 실행 시작됨\n--- 출력(현재까지) ---\n{output}"


def check_process(process_id: str) -> str:
    entry = _PROCESSES.get(process_id)
    if entry is None:
        raise ToolError(f"알 수 없는 process_id입니다 (이미 종료되었거나 존재하지 않음): {process_id}")

    exit_code = entry["popen"].poll()
    output = _read_log(process_id)
    if exit_code is not None:
        _cleanup_process(process_id)
        return f"종료됨 (exit code: {exit_code})\n--- 출력 ---\n{output}"
    return f"실행 중\n--- 출력(현재까지) ---\n{output}"


def stop_process(process_id: str) -> str:
    entry = _PROCESSES.get(process_id)
    if entry is None:
        raise ToolError(f"알 수 없는 process_id입니다 (이미 종료되었거나 존재하지 않음): {process_id}")

    popen = entry["popen"]
    if popen.poll() is None:
        popen.terminate()
        try:
            popen.wait(timeout=PROCESS_STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            popen.kill()
            popen.wait(timeout=PROCESS_STOP_TIMEOUT)
    exit_code = popen.returncode
    _cleanup_process(process_id)
    return f"process_id={process_id} 종료 완료 (exit code: {exit_code})"


# 모델이 stop_process를 잊어도 서버가 고아 프로세스로 남지 않도록, 작업 종료 시(성공/실패
# 무관) run_agent()가 이 함수를 항상 호출해 남은 백그라운드 프로세스를 정리한다.
def kill_all_processes() -> None:
    for process_id in list(_PROCESSES.keys()):
        try:
            stop_process(process_id)
        except ToolError:
            _cleanup_process(process_id)
