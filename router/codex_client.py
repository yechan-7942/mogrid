import os
import subprocess
import tempfile

# 다른 provider와 달리 HTTP API가 아니라 로컬에 설치된 `codex` CLI를 서브프로세스로
# 부른다. 인증은 CLI가 이미 들고 있는 ChatGPT 로그인(`codex login`)을 그대로 쓰므로
# mogrid는 API 키를 다루지 않는다 — ollama와 같은 "키 없는 로컬 provider" 부류다.
#
# ★주의: codex는 그 자체가 파일을 고치고 명령을 실행하는 에이전트다. mogrid에는
# 자체 tool 루프가 있으니 여기서는 순수 텍스트 생성기로만 쓴다 — 샌드박스를
# read-only로 못박고, 작업 디렉터리도 빈 임시 디렉터리로 돌려서 사용자의 저장소를
# 건드릴 수 없게 한다. 이 두 개는 성능 옵션이 아니라 안전 장치이므로 풀지 말 것.
#
# ★주의: 이 provider는 무료 티어가 아니라 사용자의 ChatGPT 에이전트 할당량을 깎는다
# (Codex + ChatGPT Work가 공유하는 풀, 5시간 롤링 + 주간 상한. 일반 채팅 몫과는 별개).
# 다른 provider와 달리 "쓰면 쓸수록 사람이 직접 쓸 몫이 줄어드는" 자원이라
# PROVIDERS에서 무료 API들보다 뒤에 둔다 (현재는 체인 중간 — fallback.py 주석 참고).
CODEX_BIN = os.getenv("MOGRID_CODEX_BIN", "codex")

# 모델은 기본적으로 사용자의 `~/.codex/config.toml` 설정을 따른다 — 사용자가 고른
# 모델을 mogrid가 임의로 덮어쓰지 않기 위해서. 굳이 고정하고 싶을 때만 env로 준다.
CODEX_MODEL = os.getenv("MOGRID_CODEX_MODEL")

# codex는 단순 completion이 아니라 에이전트라 한 응답에 내부적으로 여러 스텝을 돌 수
# 있어서 원격 provider보다 느리다. ollama만큼은 아니어도 넉넉하게 잡는다.
DEFAULT_TIMEOUT = 180


class CodexError(Exception):
    pass


def call_codex(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    # 프롬프트는 시스템 프롬프트 + 히스토리가 합쳐져 수십 KB가 되기도 한다. argv로
    # 넘기면 ARG_MAX에 걸릴 수 있으므로 프롬프트 자리에 `-`를 주고 stdin으로 넣는다.
    with tempfile.TemporaryDirectory() as workdir:
        last_message = os.path.join(workdir, "last_message.txt")
        cmd = [
            CODEX_BIN,
            "exec",
            "--ephemeral",  # 세션 파일을 디스크에 남기지 않는다 (매 호출이 일회성이라)
            "--skip-git-repo-check",
            "-s",
            "read-only",
            "-C",
            workdir,
            "--color",
            "never",
            "-o",
            last_message,
        ]
        if CODEX_MODEL:
            cmd += ["-m", CODEX_MODEL]
        cmd.append("-")

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            raise CodexError(
                f"codex CLI('{CODEX_BIN}')를 찾을 수 없습니다. "
                "설치되어 있지 않다면 이 provider는 건너뜁니다."
            )
        except subprocess.TimeoutExpired:
            raise CodexError(f"codex가 {timeout}초 내에 응답하지 않았습니다.")
        except OSError as e:
            raise CodexError(f"codex를 실행하지 못했습니다: {e}")

        if result.returncode != 0:
            # 로그인 만료·할당량 소진·모델 이름 오류가 전부 여기로 떨어진다. stderr에
            # 이유가 적혀 있으므로 그대로 올려서 `mogrid status`에 남게 한다.
            detail = (result.stderr or result.stdout or "").strip()
            raise CodexError(f"codex가 실패했습니다 (exit={result.returncode}): {detail}")

        try:
            with open(last_message, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except OSError as e:
            raise CodexError(f"codex의 응답 파일을 읽지 못했습니다: {e}")

    if not content:
        raise CodexError("codex 응답이 비어 있습니다.")
    return content


if __name__ == "__main__":
    print(call_codex("한 문장으로 너를 소개해줘."))
