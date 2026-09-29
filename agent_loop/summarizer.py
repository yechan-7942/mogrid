from agent_loop.session import PROMPT_OLDER_ENTRY_CHARS
from router.fallback import call_llm

SUMMARY_PREFIX = "[이전 작업 요약] "

# 요약 결과는 세션 기록의 맨 앞(가장 오래된 자리)에 들어가므로, 프롬프트에 실릴 때
# PROMPT_OLDER_ENTRY_CHARS로 잘린다. 이미 압축된 요약이 거기서 또 잘려 문장 중간에서
# 끊기지 않도록, 애초에 그 상한 안에 들어오는 길이를 요구한다. (넘겨도 잘릴 뿐이라
# 동작은 그대로다 — 품질 방어일 뿐 정확성 의존은 아니다.)
SUMMARY_TARGET_CHARS = PROMPT_OLDER_ENTRY_CHARS - len(SUMMARY_PREFIX) - 50


def summarize_entries(entries: list[str]) -> str:
    combined = "\n\n".join(entries)
    prompt = (
        "다음은 이전에 완료한 작업들의 기록이다. 나중에 관련 작업을 이어갈 때 참고할 수 "
        "있도록 어떤 작업을 했고 결과가 어땠는지 위주로 3문장 이내, "
        f"{SUMMARY_TARGET_CHARS}자 이내로 간결하게 요약해라. "
        "요약 결과만 답하고 다른 설명은 덧붙이지 마라.\n\n"
        f"{combined}"
    )
    return call_llm(prompt)
