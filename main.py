import argparse
import os
import sys
import webbrowser
from getpass import getpass

from dotenv import find_dotenv, load_dotenv, set_key

from agent_loop.loop import AgentLoopError, run_agent
from agent_loop.session import SessionError, load_session, save_session, trim_session

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


def run_task(task: str, session_history: list[str]) -> str | None:
    try:
        result = run_agent(task, session_history=session_history)
    except AgentLoopError as e:
        print(f"[에러] 작업을 완료하지 못했습니다: {e}", file=sys.stderr)
        return None
    print("=== 최종 결과 ===")
    print(result)
    return result


def load_session_safely() -> list[str]:
    try:
        return load_session()
    except SessionError as e:
        print(f"[경고] 이전 세션을 불러오지 못해 새로 시작합니다: {e}", file=sys.stderr)
        return []


def save_session_safely(session_history: list[str]) -> None:
    try:
        save_session(session_history)
    except SessionError as e:
        print(f"[경고] 세션을 저장하지 못했습니다: {e}", file=sys.stderr)


def run_interactive() -> None:
    print("mogrid 에이전트 (종료: exit 또는 Ctrl+D, 세션 초기화: reset)")
    session_history = load_session_safely()
    while True:
        try:
            task = input("\n작업 > ").strip()
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
            print("세션을 초기화했습니다.")
            continue
        result = run_task(task, session_history)
        if result is not None:
            session_history.append(f"작업: {task}\n결과: {result}")
            session_history = trim_session(session_history)
            save_session_safely(session_history)


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "setup":
        run_setup()
        return

    parser = argparse.ArgumentParser(
        prog="mogrid",
        description="파일을 읽고 쓰며 작업을 수행하는 에이전트 CLI",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="한 번 실행할 작업 설명. 생략하면 대화형 모드로 진입한다. "
        "'setup'을 주면 provider API 키 설정 마법사를 실행한다.",
    )
    args = parser.parse_args()

    if args.task:
        session_history = load_session_safely()
        result = run_task(args.task, session_history)
        if result is not None:
            session_history.append(f"작업: {args.task}\n결과: {result}")
            session_history = trim_session(session_history)
            save_session_safely(session_history)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
