import json
import os
import re
import sys
from typing import Callable

from agent_loop.text_utils import cap_entries
from colors import dim, yellow
from router.fallback import AllProvidersFailedError, call_llm
from tools.exec_tools import kill_all_processes
from tools.registry import TOOL_SCHEMAS, ToolError, call_tool
from tools.sandbox import PathEscapesProjectRoot
from tools.sandbox import resolve_path as _sandbox_resolve_path
from tools.skills import discover_skills, render_skill_index
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

# 캡만으로는 부족하다 — 상한에 걸리지 않아도 15개 × 3000자가 매 스텝 통째로 재전송되면
# 그 자체가 큰 비용이다(무료 티어의 분당 토큰 제한에 먼저 걸린다). 그렇다고 상한을
# 일률적으로 낮추면 모델이 방금 읽은 파일 내용을 잃어서 같은 파일을 다시 읽는 헛스텝이
# 늘어난다. 그래서 최근 RECENT_HISTORY_ENTRIES개만 원래 상한을 유지하고, 그보다 오래된
# 항목은 "무슨 일이 있었는지"만 남기면 충분하므로 훨씬 낮은 상한으로 줄인다.
RECENT_HISTORY_ENTRIES = 3
OLDER_HISTORY_ENTRY_CHARS = 600

# 약한 모델이 tool을 한 번도 호출하지 않고 "파일을 만들었다/고쳤다"고 말로만 끝내는
# 경우가 실사용 중 재현됨 (README 알려진 한계) — 프롬프트 규칙만으로는 안 지켜지므로,
# 최종 답변이 파일 작업 완료를 주장하는데 history에 write_file/edit_file/append_file
# 호출 기록이 전혀 없으면 기계적으로 걸러낸다.
FILE_MUTATING_TOOLS = {"write_file", "edit_file", "append_file"}
_FILE_ACTION_KEYWORDS = (
    "생성되었", "생성했", "생성이 완료", "만들었습니다", "만들어졌습니다",
    "작성되었", "작성했습니다", "저장되었", "저장했습니다", "수정되었", "수정했습니다",
)
_FILE_PATH_PATTERN = re.compile(r"[\w./-]+\.[a-zA-Z]{1,5}")


def claims_unverified_file_action(final_text: str, history: list[str]) -> bool:
    if any(f"tool={tool}" in entry for entry in history for tool in FILE_MUTATING_TOOLS):
        return False
    if not _FILE_PATH_PATTERN.search(final_text):
        return False
    return any(keyword in final_text for keyword in _FILE_ACTION_KEYWORDS)


# 작업 지시가 파일/함수 이름을 직접 언급하지 않고 돌려 말하면, 약한 모델이 경로를
# 추측해서 시도했다가 실패하고, 또 다른 경로를 추측하는 식으로 계속 헤매는 경우가
# 실사용 중 재현됨 (README 알려진 한계). 경로를 찾을 수 없다는 에러가 나면 그 다음
# 추측 대신 search_files를 쓰라고 결과에 기계적으로 덧붙인다.
_PATH_LOOKUP_TOOLS = {"read_file", "edit_file", "list_files"}
_NOT_FOUND_MARKER = "찾을 수 없습니다"
_NOT_FOUND_HINT = (
    " (경로를 다시 추측하지 말고, 설명에서 뽑은 키워드로 search_files를 먼저 호출해서 "
    "정확한 경로를 찾은 뒤 다시 시도해라.)"
)


def add_not_found_hint(tool_name: str, result: str) -> str:
    if tool_name in _PATH_LOOKUP_TOOLS and _NOT_FOUND_MARKER in result:
        return result + _NOT_FOUND_HINT
    return result


# 어떤 tool을 어떤 인자로 부르는지까지 매 스텝 찍으면, 사용자가 읽을 일 없는 내부 로그로
# 화면이 가득 차서 정작 최종 결과가 묻힌다. 진행 중이라는 사실만 점 하나로 알린다.
# TTY가 아니면(파이프/리다이렉트) 진행 표시는 결과물을 오염시키므로 아예 내보내지 않는다.
_PROGRESS_LABEL = "답변 생성중"


def _progress(text: str) -> None:
    if sys.stdout.isatty():
        print(dim(text), end="", flush=True)


def _progress_end() -> None:
    if sys.stdout.isatty():
        print(flush=True)


def _cap_history(history: list[str]) -> list[str]:
    return cap_entries(
        history,
        MAX_HISTORY_ENTRIES,
        MAX_HISTORY_ENTRY_CHARS,
        OLDER_HISTORY_ENTRY_CHARS,
        RECENT_HISTORY_ENTRIES,
    )


class AgentLoopError(Exception):
    pass


def build_system_prompt(skill_index: str = "") -> str:
    # 스킬이 하나도 없으면 load_skill 자체를 목록에서 뺀다. 남겨두면 약한 모델이 "있으니까
    # 일단 불러보는" 헛스텝을 쓰고, 설명글만큼의 토큰도 매 스텝 낭비된다.
    schemas = TOOL_SCHEMAS if skill_index else [t for t in TOOL_SCHEMAS if t["name"] != "load_skill"]
    tools_desc = "\n".join(
        f"- {t['name']}({', '.join(t['args'].keys())}): {t['description']}"
        for t in schemas
    )
    # 목록에는 이름과 한 줄 설명만 들어간다 — 본문까지 넣으면 매 스텝 재전송되는
    # 프롬프트가 스킬 개수만큼 불어난다. 본문은 load_skill로 필요할 때만 가져온다.
    skills_section = (
        f"사용 가능한 스킬:\n{skill_index}\n\n"
        if skill_index
        else ""
    )
    # 규칙도 같이 빼야 한다 — 스킬이 없는데 규칙만 남으면 없는 tool을 쓰라고 시키는 꼴이다.
    skill_rule = (
        "- 지금 작업과 관련된 스킬이 목록에 있으면 다른 일을 시작하기 전에 load_skill로 "
        "읽고, 거기 적힌 절차를 네 방식대로 바꾸지 말고 그대로 따라라. 관련된 스킬이 "
        "없으면 부르지 마라.\n"
        if skill_index
        else ""
    )
    # 규칙은 한 줄 = 한 규칙이 아니라 주제별로 묶는다. 이 프롬프트는 매 스텝 통째로
    # 재전송되므로(스텝 25회면 25번) 길이가 그대로 무료 티어의 분당 토큰 제한을 깎아먹는다.
    # 그래서 같은 실패를 막는 규칙끼리 병합하고, 이미 tool 설명에 적혀 있는 내용
    # (edit_file의 old_string 조건, run_command 허용 목록 등)은 지시문만 남긴다.
    return (
        "너는 파일을 읽고 쓰며 작업을 수행하는 에이전트다.\n"
        "사용 가능한 tool:\n"
        f"{tools_desc}\n\n"
        f"{skills_section}"
        "규칙:\n"
        "- 경로를 확실히 모르면 추측하지 말고 list_files(path='.')부터 확인해라. 작업 "
        "설명에 나온 프로젝트/폴더 이름이 실제 경로의 일부라고 가정하지 마라.\n"
        "- 경로를 못 찾았거나 이미 실패한 경로는 다시 시도하지도, 다른 경로를 또 추측하지도 "
        "마라. 기록을 참고하고 작업 설명 속 핵심 키워드로 search_files를 써라. 여러 폴더를 "
        "뒤져야 할 때도 list_files 반복 대신 search_files 한 번으로 찾아라.\n"
        "- search_files의 keyword는 대소문자 무시 부분 문자열이다. 여러 패턴 중 하나, 단어 "
        "경계, 줄 시작/끝처럼 부분 문자열로 표현할 수 없는 조건일 때만 regex=true를 써라.\n"
        "- 이미 있는 파일은 일부만 고칠 때 edit_file, 뒤에 덧붙일 때 append_file을 써라. "
        "write_file은 기존 내용을 전부 지우므로 새 파일을 만들거나 파일 전체를 의도적으로 "
        "갈아엎을 때만 써라 — 전체를 다시 쓰면 나머지 내용이 누락/변형될 위험이 크다. "
        "edit_file의 old_string은 앞뒤 줄을 충분히 포함해 파일 안의 한 곳만 가리키게 해라.\n"
        "- 파일이 커서 일부만 필요하면 read_file을 offset/limit으로 그 줄 범위만 읽어라.\n"
        "- 파일을 생성/수정/저장했다고 최종 답변에 적으려면 그 전에 write_file/edit_file/"
        "append_file 중 하나를 실제로 호출해서 성공해야 한다. tool을 호출하지 않고 파일 "
        "작업 완료를 주장하지 마라.\n"
        "- 폴더가 없는 경로에 쓸 때만 make_dir를 먼저 써라. 작업 설명에 없는 폴더 구조를 "
        "임의로 만들지 말고, 경로가 이미 주어졌다면 그 경로에 바로 써라.\n"
        f"{skill_rule}"
        "- 세 단계 이상 걸릴 작업은 시작할 때 update_task_list로 하위 작업 목록을 만들고, "
        "하나 끝낼 때마다 그 항목만 completed로 바꿔 전체 목록을 다시 제출해라(일부만 보내지 "
        "마라). 한두 스텝짜리 간단한 작업에는 쓰지 마라.\n"
        "- 직전 스텝과 동일한 tool/args를 다시 호출하지 마라. 필요한 정보를 다 확인했으면"
        "(파일이 없다는 것을 확인한 경우 포함) 같은 조사를 반복하지 말고 즉시 최종 답변으로 "
        "보고해라.\n"
        "- 패키지 설치, 빌드, 테스트 실행, git 조작은 run_command로 해라. exit code가 0이 "
        "아니거나 stderr가 있으면 실패로 간주하고 출력에서 원인을 찾아 다음 행동(파일 수정, "
        "재실행 등)을 정해라. 허용되지 않은 명령어라는 에러는 다른 명령어로 우회하지 말고 "
        "최종 답변에 보고해라.\n"
        "- 서버, watch 모드처럼 스스로 끝나지 않는 명령은 run_command로 실행하면 항상 "
        "타임아웃이니 start_process를 써라. 띄운 직후 성공이라고 보고하지 말고 check_process나 "
        "curl로 실제로 살아있는지 확인한 뒤, 반드시 stop_process로 종료해라.\n\n"
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
    # 스킬 탐색은 루프 밖에서 한 번만 한다 — 프롬프트는 매 스텝 다시 만들지만, 디스크를
    # 매 스텝 훑을 이유는 없다. (본문은 어차피 여기서 안 읽고 load_skill이 그때 읽는다.)
    skills, skill_errors = discover_skills()
    for path, message in skill_errors:
        print(yellow(f"[skills] 건너뜀: {path} - {message}"))
    system_prompt = build_system_prompt(render_skill_index(skills))
    history = []
    session_text = "\n\n".join(session_history) if session_history else "(없음)"
    reset_tasks()

    try:
        _progress(_PROGRESS_LABEL)
        for step in range(1, max_steps + 1):
            _progress(".")
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
                # history에 남겨서 다음 스텝에서 모델 스스로 고치게 한다. 화면에는 찍지
                # 않는다 — 다음 스텝에서 복구되는 실패라 사용자가 할 일이 없다.
                history.append(
                    f"[{step}] 에러: 이전 응답이 올바른 JSON이 아니었다 ({e}). "
                    "반드시 {\"tool\": ...} 또는 {\"final\": ...} 형식의 JSON 객체 하나만 응답해라."
                )
                history = _cap_history(history)
                continue

            if "final" in parsed:
                final_text = parsed["final"]
                if claims_unverified_file_action(final_text, history):
                    history.append(
                        f"[{step}] 에러: write_file/edit_file/append_file 중 아무것도 "
                        "호출하지 않았는데 파일을 생성/수정했다고 답변했다. 실제로 tool을 "
                        "호출해서 파일을 만든 뒤에만 완료를 보고해라."
                    )
                    history = _cap_history(history)
                    continue
                return final_text

            if "tool" in parsed:
                tool_name = parsed["tool"]
                tool_args = parsed.get("args", {})
                try:
                    reason = requires_confirmation(tool_name, tool_args)
                    if reason and confirm is not None and not confirm(reason):
                        raise ToolError(f"사용자가 승인하지 않아 실행이 취소되었습니다: {reason}")
                    result = call_tool(tool_name, tool_args)
                except ToolError as e:
                    result = f"에러: {e}"
                result = add_not_found_hint(tool_name, result)
                history.append(f"[{step}] tool={tool_name} args={tool_args} -> {result}")
                history = _cap_history(history)
                continue

            history.append(
                f"[{step}] 에러: 응답에 'tool'도 'final'도 없다: {parsed}. "
                "반드시 {\"tool\": ...} 또는 {\"final\": ...} 형식으로 응답해라."
            )
            history = _cap_history(history)

        raise AgentLoopError(f"{max_steps}스텝 안에 최종 답변을 받지 못했습니다.")
    finally:
        # 진행 표시가 줄바꿈 없이 이어지므로, 어떻게 끝나든(성공/에러/스텝초과) 여기서
        # 줄을 닫아야 최종 결과나 에러가 점 뒤에 붙지 않는다.
        _progress_end()
        # 모델이 start_process로 띄운 서버를 stop_process로 못 끄고 작업이 끝나도
        # (성공/에러/스텝초과 무관) 프로세스가 고아로 남지 않게 항상 정리한다.
        kill_all_processes()
