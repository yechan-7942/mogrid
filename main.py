import argparse
import os
import sys
import webbrowser
from getpass import getpass, getuser
from typing import Callable

from dotenv import find_dotenv, load_dotenv, set_key

from agent_loop.loop import AgentLoopError, run_agent
from agent_loop.session import MAX_SESSION_ENTRIES, SessionError, load_session, save_session, trim_session
from agent_loop.summarizer import SUMMARY_PREFIX, summarize_entries
from banner import render_welcome_banner
from colors import bold, cyan, dim, green, red, yellow
from router.fallback import PROVIDERS, AllProvidersFailedError
from router.health_check import run_all_checks
from router.usage import UsageError, load_usage
from tools.skills import discover_skills, global_skills_dir, project_skills_dir

PROVIDER_SETUP = [
    ("GROQ_API_KEY", "Groq", "https://console.groq.com/keys"),
    ("GEMINI_API_KEY", "Gemini (Google AI Studio)", "https://aistudio.google.com/app/apikey"),
    ("OPENROUTER_API_KEY", "OpenRouter", "https://openrouter.ai/keys"),
    ("MISTRAL_API_KEY", "Mistral", "https://console.mistral.ai/api-keys"),
    ("NVIDIA_API_KEY", "NVIDIA NIM", "https://build.nvidia.com/settings/api-keys"),
]


def run_setup() -> None:
    env_path = find_dotenv(usecwd=True)
    if not env_path:
        env_path = os.path.join(os.getcwd(), ".env")
        open(env_path, "a", encoding="utf-8").close()
    load_dotenv(env_path)

    print(f"API 키는 {env_path}에 저장된다.\n")
    print(
        "각 provider마다 키 발급 페이지를 브라우저로 열어줄 테니, 로그인 후 발급받은 "
        "키를 여기에 붙여넣어라. 로그인/키 발급은 직접 해야 한다 — 필요 없는 provider는 "
        "Enter로 건너뛰면 된다."
    )

    for env_var, label, url in PROVIDER_SETUP:
        if os.getenv(env_var):
            answer = (
                input(f"\n{label}({env_var})은 이미 설정되어 있다. 새로 발급받아 교체할까? (y/N): ")
                .strip()
                .lower()
            )
            if answer != "y":
                continue

        print(f"\n[{label}] 키 발급 페이지를 연다: {url}")
        if not webbrowser.open(url):
            print("브라우저를 자동으로 열지 못했다. 위 URL을 직접 열어라.")

        key = getpass(f"{label} API 키를 붙여넣어라 (건너뛰려면 Enter): ").strip()
        if not key:
            print(f"{label} 건너뜀.")
            continue

        set_key(env_path, env_var, key)
        os.chmod(env_path, 0o600)
        os.environ[env_var] = key
        print(f"{label} 저장 완료.")

    print("\n설정 완료. mogrid를 실행하면 방금 저장한 키들이 자동으로 로드된다.")


_STATUS_LABELS = {"ok": "OK", "missing": "누락", "error": "에러", "skipped": "건너뜀"}
_STATUS_COLORS = {"ok": green, "missing": red, "error": red, "skipped": dim}


def run_check_models() -> int:
    print(bold(cyan("provider별 기본 모델 가용성 확인 중...\n")))
    exit_code = 0
    for provider, status, detail in run_all_checks():
        color = _STATUS_COLORS.get(status, dim)
        label = _STATUS_LABELS.get(status, status)
        print(f"[{color(label)}] {provider}: {detail}")
        if status in ("missing", "error"):
            exit_code = 1
    return exit_code


_PROVIDER_DISPLAY_NAMES = {
    "groq": "Groq",
    "gemini": "Gemini",
    "openrouter": "OpenRouter",
    "mistral": "Mistral",
    "nvidia": "NVIDIA NIM",
    "ollama": "Ollama",
}


def run_status() -> int:
    try:
        data = load_usage()
    except UsageError as e:
        print(red(f"[에러] 사용량 파일을 읽지 못했습니다: {e}"), file=sys.stderr)
        return 1

    print(bold(cyan("provider별 사용량 (mogrid를 통해 호출된 기록 기준)\n")))
    for name, _, _ in PROVIDERS:
        label = _PROVIDER_DISPLAY_NAMES.get(name, name)
        record = data.get(name)
        if not record:
            print(f"[{dim('기록 없음')}] {label}")
            continue

        today = f"오늘 성공 {record['today_success']}회"
        if record["today_fail"]:
            today += f", 실패 {record['today_fail']}회"
        total = f"전체 성공 {record['total_success']}회"
        if record["total_fail"]:
            total += f", 실패 {record['total_fail']}회"
        last_used = record.get("last_used") or "-"

        print(f"[{green('사용됨')}] {label}: {today} / {total} (마지막 성공: {last_used})")
        if record.get("last_error"):
            print(dim(f"    마지막 실패 사유: {record['last_error'][:200]}"))

    print(dim("\n실제 provider 쪽 잔여 할당량이 아니라, mogrid를 거쳐 호출된 횟수입니다."))
    return 0


def run_skills() -> int:
    skills, errors = discover_skills()

    print(bold(cyan("사용 가능한 스킬\n")))
    if not skills:
        print(dim("등록된 스킬이 없습니다."))
    for skill in sorted(skills.values(), key=lambda s: s.name):
        origin = "프로젝트" if skill.source == "project" else "전역"
        print(f"[{green(origin)}] {bold(skill.name)}: {skill.description}")
        print(dim(f"    {skill.path}"))

    # 깨진 스킬은 조용히 빠지면 "왜 안 불러지지"로 한참 헤매게 된다 — 이 명령의 존재
    # 이유 절반이 이 목록이다.
    if errors:
        print(red(bold("\n읽지 못한 스킬 파일\n")))
        for path, message in errors:
            print(f"[{red('에러')}] {path}: {message}")

    print(
        dim(
            f"\n스킬 위치: {project_skills_dir()} (프로젝트), {global_skills_dir()} (전역). "
            "이름이 같으면 프로젝트 쪽이 우선합니다."
        )
    )
    return 1 if errors else 0


def interactive_confirm(reason: str) -> bool:
    answer = input(f"\n{yellow(bold('[확인 필요]'))} {reason}\n진행할까요? (y/N): ").strip().lower()
    return answer == "y"


def one_shot_confirm(auto_approve: bool):
    def _confirm(reason: str) -> bool:
        if auto_approve:
            return True
        print(
            red(f"[차단됨] 확인이 필요한 작업이라 비대화형 모드에서는 실행하지 않았습니다: {reason}"),
            file=sys.stderr,
        )
        print(
            dim("실행하려면 --yes 옵션이나 MOGRID_AUTO_APPROVE=1 환경변수를 사용하세요."),
            file=sys.stderr,
        )
        return False

    return _confirm


def has_any_provider_key() -> bool:
    return any(os.getenv(env_var) for env_var, _, _ in PROVIDER_SETUP)


_no_key_hint_shown = False


def print_no_key_hint_if_needed() -> None:
    # 키가 하나도 없으면 fallback이 provider 5개를 순서대로 다 찍어보고 나서야
    # 실패한다 - 그 전에 원인을 바로 알려준다. 프로세스당 한 번만 보여준다
    # (대화형 모드에서 작업마다 반복 출력되면 소음이 된다).
    global _no_key_hint_shown
    if _no_key_hint_shown or has_any_provider_key():
        return
    _no_key_hint_shown = True
    print(
        yellow(
            "[안내] 설정된 provider API 키가 없습니다. 'mogrid setup'으로 키를 등록하세요. "
            "(로컬 Ollama가 실행 중이면 그걸로 시도합니다.)"
        ),
        file=sys.stderr,
    )


def run_task(
    task: str, session_history: list[str], confirm: Callable[[str], bool] | None = None
) -> str | None:
    print_no_key_hint_if_needed()
    try:
        result = run_agent(task, session_history=session_history, confirm=confirm)
    except AgentLoopError as e:
        print(red(f"[에러] 작업을 완료하지 못했습니다: {e}"), file=sys.stderr)
        return None
    print(green(bold("\n=== 최종 결과 ===")))
    print(result)
    return result


def summarize_session_if_needed(session_history: list[str]) -> list[str]:
    if len(session_history) <= MAX_SESSION_ENTRIES:
        return trim_session(session_history)

    # 그냥 자르면 오래된 작업 기록이 통째로 사라진다. 넘치는 만큼만 LLM으로 요약해서
    # 한 항목으로 압축하고, 최근 기록은 그대로 유지한다.
    keep_count = MAX_SESSION_ENTRIES - 1
    to_summarize = session_history[:-keep_count]
    recent = session_history[-keep_count:]
    try:
        summary = summarize_entries(to_summarize)
    except AllProvidersFailedError as e:
        print(yellow(f"[경고] 세션 요약에 실패해 오래된 기록을 요약 없이 정리합니다: {e}"), file=sys.stderr)
        return trim_session(session_history)
    return trim_session([f"{SUMMARY_PREFIX}{summary}"] + recent)


def load_session_safely() -> list[str]:
    try:
        return load_session()
    except SessionError as e:
        print(yellow(f"[경고] 이전 세션을 불러오지 못해 새로 시작합니다: {e}"), file=sys.stderr)
        return []


def save_session_safely(session_history: list[str]) -> None:
    try:
        save_session(session_history)
    except SessionError as e:
        print(yellow(f"[경고] 세션을 저장하지 못했습니다: {e}"), file=sys.stderr)


def run_interactive() -> None:
    try:
        user = getuser()
    except OSError:
        user = None
    print(render_welcome_banner(user=user))
    session_history = load_session_safely()
    while True:
        try:
            task = input(f"\n{bold(cyan('작업 >'))} ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break
        if not task:
            continue
        if task in ("exit", "quit"):
            break
        if task == "reset":
            session_history = []
            save_session_safely(session_history)
            print(dim("세션을 초기화했습니다."))
            continue
        if task == "status":
            run_status()
            continue
        if task == "skills":
            run_skills()
            continue
        result = run_task(task, session_history, confirm=interactive_confirm)
        if result is not None:
            session_history.append(f"작업: {task}\n결과: {result}")
            session_history = summarize_session_if_needed(session_history)
            save_session_safely(session_history)


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "setup":
        run_setup()
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "check-models":
        sys.exit(run_check_models())
    if len(sys.argv) >= 2 and sys.argv[1] == "status":
        sys.exit(run_status())
    if len(sys.argv) >= 2 and sys.argv[1] == "skills":
        sys.exit(run_skills())

    parser = argparse.ArgumentParser(
        prog="mogrid",
        description="파일을 읽고 쓰며 작업을 수행하는 에이전트 CLI",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="한 번 실행할 작업 설명. 생략하면 대화형 모드로 진입한다. "
        "'setup'을 주면 provider API 키 설정 마법사를, 'check-models'를 주면 "
        "각 provider의 기본 모델이 아직 살아있는지, 'status'를 주면 provider별 "
        "호출 사용량을, 'skills'를 주면 등록된 스킬 목록을 확인한다.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="한 번 실행 모드에서 확인이 필요한 작업(run_command, 기존 파일 덮어쓰기)도 "
        "묻지 않고 진행한다. 대화형 모드에는 영향 없음(항상 직접 확인받음).",
    )
    args = parser.parse_args()

    if args.task:
        auto_approve = args.yes or os.environ.get("MOGRID_AUTO_APPROVE") == "1"
        session_history = load_session_safely()
        result = run_task(args.task, session_history, confirm=one_shot_confirm(auto_approve))
        if result is not None:
            session_history.append(f"작업: {args.task}\n결과: {result}")
            session_history = summarize_session_if_needed(session_history)
            save_session_safely(session_history)
        else:
            # run_task가 None을 반환했다는 건 작업이 실패했다는 뜻이다 — 여기서
            # exit code를 0으로 두면 스크립트/CI에서 성공 여부를 판단할 수 없다.
            sys.exit(1)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
