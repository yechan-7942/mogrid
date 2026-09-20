import os
import sys

# 파이프로 리다이렉트되거나(비TTY) NO_COLOR가 설정된 환경에서는 ANSI 코드가 그대로
# 텍스트에 섞여 나가면 안 되므로 자동으로 끈다.
_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

_CODES = {
    "dim": "2",
    "bold": "1",
    "cyan": "36",
    "yellow": "33",
    "green": "32",
    "red": "31",
}


def _wrap(code_name: str, text: str) -> str:
    if not _ENABLED:
        return text
    return f"\033[{_CODES[code_name]}m{text}\033[0m"


def dim(text: str) -> str:
    return _wrap("dim", text)


def bold(text: str) -> str:
    return _wrap("bold", text)


def cyan(text: str) -> str:
    return _wrap("cyan", text)


def yellow(text: str) -> str:
    return _wrap("yellow", text)


def green(text: str) -> str:
    return _wrap("green", text)


def red(text: str) -> str:
    return _wrap("red", text)
