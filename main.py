import argparse
import sys

from agent_loop.loop import AgentLoopError, run_agent
from agent_loop.session import SessionError, load_session, save_session, trim_session


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
    parser = argparse.ArgumentParser(
        prog="mogrid",
        description="파일을 읽고 쓰며 작업을 수행하는 에이전트 CLI",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="한 번 실행할 작업 설명. 생략하면 대화형 모드로 진입한다.",
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
