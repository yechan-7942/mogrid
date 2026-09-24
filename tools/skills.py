"""스킬: 작업 절차를 마크다운 파일로 적어두고, 관련된 작업일 때만 본문을 불러다 쓰는 구조.

mogrid는 무료 티어 모델 위에서 돌고, 시스템 프롬프트는 매 스텝 통째로 다시 전송된다.
그래서 스킬 본문을 전부 프롬프트에 싣는 방식은 쓸 수 없다 — 스킬 3~4개만 있어도 매 스텝
수천 토큰이 새는 셈이라 컨텍스트/rate limit에 그대로 부딪힌다. 대신 두 단계로 나눈다:

1. 인덱스(이름 + 한 줄 설명)만 시스템 프롬프트에 상주 — 스킬 하나당 수십 자.
2. 본문은 모델이 `load_skill(name)`을 호출했을 때만 history로 들어온다.

즉 "어떤 스킬이 있는지"는 항상 알지만 "그 안에 뭐라고 적혀 있는지"는 필요할 때만 읽는다.
"""

import os

from tools.file_tools import ToolError
from tools.sandbox import project_root

# 프로젝트 전용 스킬과 어디서나 쓰는 전역 스킬. 같은 이름이면 프로젝트 쪽이 이긴다
# (특정 저장소의 사정에 맞춘 절차가 범용 절차보다 우선해야 하므로).
PROJECT_SKILLS_SUBDIR = os.path.join(".mogrid", "skills")
DEFAULT_GLOBAL_SKILLS_DIR = os.path.expanduser("~/.mogrid/skills")

# sandbox.PROJECT_ROOT_ENV와 같은 이유로 env로 덮어쓸 수 있게 한다. 상수로 고정하면
# 테스트가 실행하는 사람의 실제 홈 디렉터리 내용에 따라 결과가 달라진다.
GLOBAL_SKILLS_DIR_ENV = "MOGRID_SKILLS_DIR"

# 스킬 본문은 load_skill 결과로 history에 들어가고, history는 매 스텝 프롬프트에 다시
# 삽입된다. 본문 하나가 길면 그 비용을 남은 스텝 내내 반복해서 물게 되므로 상한을 둔다.
MAX_SKILL_BODY_CHARS = 8000

SKILL_FILE_NAME = "SKILL.md"


class SkillError(ToolError):
    """ToolError를 상속해서, load_skill이 던지면 agent_loop의 기존 tool 에러 처리가
    그대로 받아 모델에게 되돌려준다 (루프를 죽이지 않고 다음 스텝에서 고치게 한다).
    별도 타입인 건 `mogrid skills`가 스킬 문제만 따로 구분해서 보여주기 위해서다."""


class Skill:
    def __init__(self, name: str, description: str, body: str, path: str, source: str):
        self.name = name
        self.description = description
        self.body = body
        self.path = path
        self.source = source  # "project" 또는 "global" — 이름 충돌 시 어느 쪽이 이겼는지 표시용

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, source={self.source!r})"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """'---'로 감싼 `key: value` 블록과 본문을 분리한다.

    PyYAML을 끌어오지 않으려고 직접 파싱한다 — 스킬 frontmatter에 필요한 건 name과
    description 두 개의 평범한 문자열뿐이라, 전체 YAML 문법을 지원할 이유가 없다.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError("frontmatter가 없습니다 ('---'로 시작해야 합니다).")

    meta = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1 :]).strip()
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise SkillError(f"frontmatter의 '{line.strip()}' 줄이 'key: value' 형식이 아닙니다.")
        meta[key.strip()] = value.strip()

    raise SkillError("frontmatter가 닫히지 않았습니다 ('---'로 끝나야 합니다).")


def _skill_name_from_path(path: str) -> str:
    """`<name>.md`와 `<name>/SKILL.md` 두 형태를 모두 지원한다.

    디렉터리 형태는 스킬이 참고 파일(스크립트, 템플릿 등)을 같이 끼고 다닐 수 있게 해준다.
    """
    if os.path.basename(path) == SKILL_FILE_NAME:
        return os.path.basename(os.path.dirname(path))
    return os.path.splitext(os.path.basename(path))[0]


def _load_skill_file(path: str, source: str) -> Skill:
    expected_name = _skill_name_from_path(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise SkillError(f"스킬 파일을 읽을 수 없습니다: {path} ({e})")

    meta, body = parse_frontmatter(text)

    description = meta.get("description", "").strip()
    if not description:
        raise SkillError("frontmatter에 description이 없습니다 (모델이 이 줄만 보고 스킬을 고른다).")
    if not body:
        raise SkillError("본문이 비어 있습니다.")

    # name이 파일 위치와 다르면 인덱스에 뜨는 이름과 load_skill로 부르는 이름이 어긋나
    # "분명 목록에는 있는데 불러지지 않는" 상태가 된다. 조용히 한쪽을 고르지 말고 막는다.
    name = meta.get("name", "").strip()
    if name and name != expected_name:
        raise SkillError(
            f"frontmatter의 name('{name}')이 파일 이름에서 유추한 이름('{expected_name}')과 "
            "다릅니다. 둘을 같게 맞추거나 name을 지우세요."
        )

    if len(body) > MAX_SKILL_BODY_CHARS:
        raise SkillError(
            f"본문이 너무 깁니다 ({len(body)}자 > {MAX_SKILL_BODY_CHARS}자). "
            "절차를 줄이거나 여러 스킬로 나누세요."
        )

    return Skill(expected_name, description, body, path, source)


def _skill_files_in(directory: str) -> list[str]:
    if not os.path.isdir(directory):
        return []
    paths = []
    try:
        for entry in sorted(os.listdir(directory)):
            full = os.path.join(directory, entry)
            if os.path.isdir(full):
                nested = os.path.join(full, SKILL_FILE_NAME)
                if os.path.isfile(nested):
                    paths.append(nested)
            elif entry.endswith(".md"):
                paths.append(full)
    except OSError:
        # 권한 문제 등으로 목록을 못 읽는 건 "스킬이 없는 것"과 같게 취급한다 — 스킬은
        # 부가 기능이라, 못 읽는다고 에이전트 실행 자체를 막을 이유가 없다.
        return []
    return paths


def project_skills_dir() -> str:
    return os.path.join(project_root(), PROJECT_SKILLS_SUBDIR)


def global_skills_dir() -> str:
    return os.environ.get(GLOBAL_SKILLS_DIR_ENV) or DEFAULT_GLOBAL_SKILLS_DIR


def discover_skills() -> tuple[dict[str, Skill], list[tuple[str, str]]]:
    """(이름 -> Skill, [(경로, 에러 메시지)]) 를 반환한다.

    깨진 스킬 하나가 나머지 전부를 못 쓰게 만들면 안 되므로, 실패한 파일은 건너뛰되
    조용히 버리지 않고 두 번째 값으로 같이 돌려준다 (`mogrid skills`가 이걸 보여준다).
    """
    skills: dict[str, Skill] = {}
    errors: list[tuple[str, str]] = []

    # 전역을 먼저 넣고 프로젝트로 덮어써서, 같은 이름이면 프로젝트 쪽이 남게 한다.
    for source, directory in (("global", global_skills_dir()), ("project", project_skills_dir())):
        for path in _skill_files_in(directory):
            try:
                skill = _load_skill_file(path, source)
            except SkillError as e:
                errors.append((path, str(e)))
                continue
            skills[skill.name] = skill

    return skills, errors


def render_skill_index(skills: dict[str, Skill]) -> str:
    """시스템 프롬프트에 들어갈 목록. 본문은 절대 여기 넣지 않는다."""
    return "\n".join(f"- {s.name}: {s.description}" for s in sorted(skills.values(), key=lambda s: s.name))


def load_skill(name: str) -> str:
    """모델이 호출하는 tool. 이름이 틀리면 있는 목록을 같이 알려줘서 재추측을 줄인다."""
    if not isinstance(name, str) or not name.strip():
        raise SkillError("스킬 이름을 지정해야 합니다.")
    name = name.strip()

    skills, _ = discover_skills()
    skill = skills.get(name)
    if skill is None:
        available = ", ".join(sorted(skills)) or "(없음)"
        raise SkillError(f"'{name}' 스킬을 찾을 수 없습니다. 사용 가능한 스킬: {available}")

    return f"[스킬: {skill.name}]\n{skill.body}"
