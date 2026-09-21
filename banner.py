import os
import shutil
import unicodedata
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from colors import bold, cyan, dim

_PROVIDER_ENV_VARS = [
    ("groq", "GROQ_API_KEY"),
    ("gemini", "GEMINI_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
    ("mistral", "MISTRAL_API_KEY"),
    ("nvidia", "NVIDIA_API_KEY"),
]
_TOTAL_PROVIDERS = len(_PROVIDER_ENV_VARS) + 1  # ollama는 로컬 서버라 키 없이도 후보에 포함


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _truncate(text: str, max_width: int) -> str:
    if _display_width(text) <= max_width:
        return text
    result = ""
    for ch in text:
        if _display_width(result + ch) > max_width - 1:
            return result + "…"
        result += ch
    return result


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _configured_provider_count() -> int:
    return sum(1 for _, env_var in _PROVIDER_ENV_VARS if os.getenv(env_var)) + 1


def _mogrid_version() -> str:
    try:
        return _pkg_version("mogrid")
    except PackageNotFoundError:
        return "dev"


def _abbreviate_home(path: str) -> str:
    home = os.path.expanduser("~")
    if path == home or path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


def render_welcome_banner(user: str | None = None) -> str:
    terminal_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    # inner: "│"와 "│" 사이(테두리 문자 제외)의 실제 내용 폭. top/bottom 테두리의
    # "─" 개수와 각 content 줄의 패딩 폭을 항상 이 값 하나로 맞춰야 좌우 테두리가
    # 어긋나지 않는다.
    inner = max(48, min(terminal_width - 4, 66))

    title = f" mogrid v{_mogrid_version()} "
    title_dashes = max(0, inner - 1 - _display_width(title))
    top = "╭─" + bold(cyan(title)) + "─" * title_dashes + "╮"
    bottom = "╰" + "─" * inner + "╯"

    user = user or "사용자"
    provider_count = _configured_provider_count()
    cwd = _abbreviate_home(os.getcwd())

    rows: list[tuple[str, bool]] = [
        ("", False),
        (f"반가워요, {user}님! mogrid와 함께 시작해요.", True),
        ("", False),
        ("Tips", False),
        ("  · mogrid setup         provider API 키 설정", False),
        ("  · mogrid check-models  모델 가용성 점검", False),
        ("  · reset / exit         세션 초기화 / 종료", False),
        ("", False),
        (f"provider {provider_count}/{_TOTAL_PROVIDERS} 사용 가능  ·  {cwd}", False),
    ]

    lines = [top]
    for text, emphasize in rows:
        text = _truncate(text, inner - 1)
        padded = _pad(f" {text}", inner)
        styled = bold(padded) if emphasize else dim(padded)
        lines.append(f"│{styled}│")
    lines.append(bottom)
    return "\n".join(lines)
