import json
import os
from typing import Callable

from agent_loop.text_utils import cap_entries
from router.fallback import AllProvidersFailedError, call_llm
from tools.exec_tools import kill_all_processes
from tools.registry import TOOL_SCHEMAS, ToolError, call_tool
from tools.sandbox import PathEscapesProjectRoot
from tools.sandbox import resolve_path as _sandbox_resolve_path
from tools.task_tracker import render_task_list, reset_tasks

# 확인 없이 실행하면 되돌리기 어렵거나 프로젝트 밖(예: git push)에 흔적을 남길 수 있는
# tool. write_file은 새 파일 생성은 안전하지만 "이미 있는 파일을 덮어쓰는" 경우만 위험하므로
# 별도로 검사한다.
CONFIRM_REQUIRED_TOOLS = {"run_command"}

MAX_STEPS = 25
# run_command 등 tool 결과가 길어질 수 있어, session_history와 같은 이유로
# 이번 작업 안의 history도 개수/길이를 캡 씌운다 (그렇지 않으면 스텝이 늘어날수록
# 매 프롬프트에 재삽입되는 history가 무한정 커져 컨텍스트/rate limit을 넘길 수 있다).
MAX_HISTORY_ENTRIES = 15
MAX_HISTORY_ENTRY_CHARS = 3000


class AgentLoopError(Exception):
    pass


def build_system_prompt() -> str:
    tools_desc = "\n".join(
        f"- {t['name']}({', '.join(t['args'].keys())}): {t['description']}"
        for t in TOOL_SCHEMAS
    )
    return (
        "너는 파일을 읽고 쓰며 작업을 수행하는 에이전트다.\n"
        "다음 tool들을 사용할 수 있다:\n"
        f"{tools_desc}\n\n"
        "규칙:\n"
        "- 파일 경로를 확실히 모르면 절대 추측하지 말고, "
        "list_files(path='.')로 현재 위치부터 확인해라.\n"
        "- 작업 설명에 등장하는 프로젝트/폴더 이름을 실제 경로의 일부라고 가정하지 마라.\n"
        "- 같은 경로가 이미 실패했다면 그 경로를 다시 시도하지 말고, "
        "지금까지의 기록을 참고해 다른 경로를 시도해라.\n"
        "- 파일이 어느 폴더에 있는지 몰라서 여러 폴더를 돌아다니며 찾아야 할 것 같으면, "
        "list_files를 반복 호출하지 말고 search_files(keyword)로 한 번에 찾아라.\n"
        "- 기존 파일의 내용을 유지한 채로 뒤에 내용을 덧붙여야 하면 write_file이 아니라 "
        "append_file을 사용해라. write_file은 기존 내용을 완전히 지우고 덮어쓴다.\n"
        "- 이미 존재하는 파일의 일부만 고칠 때는 write_file로 파일 전체를 다시 쓰지 말고 "
        "edit_file을 사용해라. write_file로 전체를 다시 쓰면 나머지 내용을 그대로 재현하는 "
        "과정에서 실수로 내용이 누락/변형될 위험이 크다. write_file은 새 파일을 만들거나 "
        "파일 전체를 의도적으로 갈아엎을 때만 사용해라.\n"
        "- edit_file의 old_string은 파일 안에 있는 그대로 정확히 일치해야 하고, 대상이 "
        "여러 번 등장하면 실패한다. 위치를 특정할 수 있도록 앞뒤 줄을 충분히 포함시켜라.\n"
        "- 파일이 커서 특정 부분만 필요하면 read_file 전체를 다 읽지 말고 offset/limit으로 "
        "필요한 줄 범위만 읽어라.\n"
        "- search_files의 keyword는 기본적으로 대소문자 무시 부분 문자열이다. 여러 패턴 중 "
        "하나, 단어 경계, 줄 시작/끝처럼 부분 문자열로 표현할 수 없는 조건을 찾을 때만 "
        "regex=true로 정규식을 사용해라.\n"
        "- 세 단계 이상 걸릴 것 같은 작업을 시작할 때는 update_task_list로 하위 작업 "
        "목록을 먼저 만들어라. 하위 작업을 하나 끝낼 때마다 그 항목만 completed로 바꿔서 "
        "전체 목록을 다시 제출해라 (매번 목록 전체를 통째로 제출, 일부만 보내지 마라). "
        "한두 스텝짜리 간단한 작업에는 쓰지 마라.\n"
        "- 존재하지 않는 폴더 경로에 파일을 쓰려고 하면 먼저 make_dir로 폴더를 만든 뒤 "
        "write_file/append_file을 사용해라.\n"
        "- 작업 설명에 없는 폴더 구조를 임의로 새로 만들지 마라. 특히 파일 경로가 이미 "
        "명확히 주어졌다면 make_dir를 쓰지 말고 그 경로에 바로 써라.\n"
        "- 이미 필요한 정보를 다 확인했다면 (예: 파일이 존재하지 않는다는 것을 확인한 "
        "경우 포함) 같은 조사를 반복하지 말고 즉시 최종 답변으로 보고해라.\n"
        "- 바로 직전 스텝과 완전히 동일한 tool/args를 다시 호출하지 마라. 이미 그 결과를 "
        "알고 있으니 기록을 참고해서 다음 행동을 결정해라.\n"
        "- 패키지 설치, 빌드, 테스트 실행, git 조작이 필요하면 run_command를 사용해라. "
        "run_command는 허용된 명령어만 실행되고 프로젝트 폴더를 벗어날 수 없다 — 허용되지 "
        "않은 명령어라는 에러가 오면 다른 명령어로 우회하려 하지 말고 그 사실을 최종 답변에 "
        "보고해라.\n"
        "- run_command 실행 결과에 exit code가 0이 아니거나 stderr가 있으면 실패로 간주하고, "
        "출력 내용을 근거로 원인을 파악해 다음 행동(파일 수정, 재실행 등)을 결정해라.\n"
        "- 서버 실행, watch 모드처럼 스스로 끝나지 않고 계속 떠 있어야 하는 명령은 "
        "run_command로 실행하지 마라. run_command는 명령이 끝날 때까지 기다리는 구조라 "
        "타임아웃으로 항상 실패한다. 이런 경우 start_process를 사용해라.\n"
        "- start_process로 띄운 뒤에는 바로 성공이라고 보고하지 마라. 필요하면 잠시 후 "
        "check_process로 아직 살아있는지/무슨 출력이 났는지 확인하고, curl 등으로 실제 "
        "응답을 확인해라. 확인이 끝났으면 반드시 stop_process로 종료해라.\n\n"
        "매 턴마다 반드시 아래 두 형식 중 하나로만, JSON 객체 하나만 응답해라. "
        "설명이나 다른 텍스트를 절대 덧붙이지 마라.\n"
        '1) tool 호출: {"tool": "<tool 이름>", "args": {...}}\n'
        '2) 최종 답변: {"final": "<최종 답변>"}\n'
    )


def extract_json(text: str) -> dict:
    start = text.find("{")
    if start == -1:
        raise AgentLoopError(f"모델 응답에서 JSON을 찾을 수 없습니다: {text}")
    # 첫 '{'부터 마지막 '}'까지를 통째로 파싱하면, 그 뒤에 다른 내용이 더 붙었을 때
    # (예: Qwen 같은 hybrid-thinking 모델이 </think> 태그나 JSON을 중복으로 더 뱉는
    # 경우) "Extra data" 에러로 통째로 실패한다. raw_decode는 첫 번째 완전한 JSON
    # 값만 파싱하고 그 뒤는 무시하므로 이런 꼬리 데이터에 안전하다.
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as e:
        raise AgentLoopError(f"모델 응답 JSON 파싱 실패: {e} / raw={text}")
    return obj


def requires_confirmation(tool_name: str, tool_args: dict) -> str | None:
    if tool_name in CONFIRM_REQUIRED_TOOLS:
        return f"명령 실행: {tool_args.get('command', '')}"
    if tool_name == "write_file":
        path = tool_args.get("path", "")
        try:
            target = _sandbox_resolve_path(path)
        except PathEscapesProjectRoot:
            return None  # 샌드박스 밖 경로는 call_tool에서 어차피 에러가 나므로 확인 불필요
        if os.path.exists(target):
            return f"기존 파일 덮어쓰기: {path}"
    return None


def run_agent(
    task: str,
    max_steps: int = MAX_STEPS,
    session_history: list[str] | None = None,
    confirm: Callable[[str], bool] | None = None,
) -> str:
    system_prompt = build_system_prompt()
    history = []
    session_text = "\n\n".join(session_history) if session_history else "(없음)"
    reset_tasks()

    try:
        for step in range(1, max_steps + 1):
            history_text = "\n".join(history) if history else "(없음)"
            prompt = (
                f"{system_prompt}\n"
                f"이 세션에서 이전에 완료한 작업들:\n{session_text}\n\n"
                f"이번 작업: {task}\n\n"
                f"현재 하위 작업 목록:\n{render_task_list()}\n\n"
                f"이번 작업 안에서 지금까지 기록:\n{history_text}\n\n"
                "다음 행동을 JSON으로 응답해라."
            )

            try:
                raw_response = call_llm(prompt)
            except AllProvidersFailedError as e:
                # 개별 provider 장애는 fallback이 이미 흡수한다 — 여기까지 올라왔다는 건
                # 전부 다 실패했다는 뜻이라, 재시도해도 나아질 여지가 없다. history에
                # 남겨서 재시도를 반복하기보다 바로 실패로 보고한다.
                raise AgentLoopError(f"모든 provider가 실패해서 작업을 진행할 수 없습니다: {e}")

            try:
                parsed = extract_json(raw_response)
            except AgentLoopError as e:
                # 모델이 매 턴 만들어내는 형식 오류는 provider 장애와 달리 "다시 시도하면
                # 되는" 종류다 — 여기서 바로 죽이면 이미 성공한 이전 스텝들까지 다 날아가니,
                # history에 남겨서 다음 스텝에서 모델 스스로 고치게 한다.
                print(f"[agent_loop] step {step}: JSON 파싱 실패 - {e}")
                history.append(
                    f"[{step}] 에러: 이전 응답이 올바른 JSON이 아니었다 ({e}). "
                    "반드시 {\"tool\": ...} 또는 {\"final\": ...} 형식의 JSON 객체 하나만 응답해라."
                )
                history = cap_entries(history, MAX_HISTORY_ENTRIES, MAX_HISTORY_ENTRY_CHARS)
                continue

            if "final" in parsed:
                return parsed["final"]

            if "tool" in parsed:
                tool_name = parsed["tool"]
                tool_args = parsed.get("args", {})
                print(f"[agent_loop] step {step}: {tool_name}({tool_args}) 호출")
                try:
                    reason = requires_confirmation(tool_name, tool_args)
                    if reason and confirm is not None and not confirm(reason):
                        raise ToolError(f"사용자가 승인하지 않아 실행이 취소되었습니다: {reason}")
                    result = call_tool(tool_name, tool_args)
                except ToolError as e:
                    result = f"에러: {e}"
                history.append(f"[{step}] tool={tool_name} args={tool_args} -> {result}")
                history = cap_entries(history, MAX_HISTORY_ENTRIES, MAX_HISTORY_ENTRY_CHARS)
                continue

            print(f"[agent_loop] step {step}: 응답에 'tool'도 'final'도 없음 - {parsed}")
            history.append(
                f"[{step}] 에러: 응답에 'tool'도 'final'도 없다: {parsed}. "
                "반드시 {\"tool\": ...} 또는 {\"final\": ...} 형식으로 응답해라."
            )
            history = cap_entries(history, MAX_HISTORY_ENTRIES, MAX_HISTORY_ENTRY_CHARS)

        raise AgentLoopError(f"{max_steps}스텝 안에 최종 답변을 받지 못했습니다.")
    finally:
        # 모델이 start_process로 띄운 서버를 stop_process로 못 끄고 작업이 끝나도
        # (성공/에러/스텝초과 무관) 프로세스가 고아로 남지 않게 항상 정리한다.
        kill_all_processes()
