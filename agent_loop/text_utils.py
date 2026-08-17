def cap_entries(entries: list[str], max_entries: int, max_chars: int) -> list[str]:
    capped = [
        entry if len(entry) <= max_chars else entry[:max_chars] + " …(생략됨)"
        for entry in entries
    ]
    return capped[-max_entries:]
