def cap_entries(
    entries: list[str],
    max_entries: int,
    max_chars: int,
    older_max_chars: int | None = None,
    recent_count: int = 0,
) -> list[str]:
    """오래된 항목부터 버리고, 남은 항목도 길이 상한으로 자른다.

    older_max_chars를 주면 최근 recent_count개만 max_chars를 쓰고 그보다 오래된 항목은
    더 낮은 상한으로 자른다. 프롬프트는 매 스텝 통째로 재전송되므로 히스토리가 그대로
    토큰 비용이 되는데, 모델이 실제로 보고 행동하는 건 방금 읽은 파일 내용 같은 최근
    항목이고 오래된 항목은 "무슨 일이 있었는지"만 알면 충분하다. 그래서 최근 것은
    그대로 두고 오래된 것만 강하게 줄인다.

    older_max_chars가 없으면 전부 같은 상한으로 자른다.
    """
    kept = entries[-max_entries:]
    if older_max_chars is None:
        return [_truncate(entry, max_chars) for entry in kept]

    # 최근 recent_count개만 넉넉한 상한을 쓴다. recent_count가 0이면 전부 낮은 상한.
    older_end = len(kept) - recent_count
    return [
        _truncate(entry, max_chars if i >= older_end else older_max_chars)
        for i, entry in enumerate(kept)
    ]


def _truncate(entry: str, max_chars: int) -> str:
    if len(entry) <= max_chars:
        return entry
    return entry[:max_chars] + " …(생략됨)"
