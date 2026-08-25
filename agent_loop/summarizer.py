from router.fallback import call_llm

SUMMARY_PREFIX = "[이전 작업 요약] "


def summarize_entries(entries: list[str]) -> str:
    combined = "\n\n".join(entries)
    prompt = (
        "다음은 이전에 완료한 작업들의 기록이다. 나중에 관련 작업을 이어갈 때 참고할 수 "
        "있도록 어떤 작업을 했고 결과가 어땠는지 위주로 5문장 이내로 간결하게 요약해라. "
        "요약 결과만 답하고 다른 설명은 덧붙이지 마라.\n\n"
        f"{combined}"
    )
    return call_llm(prompt)
