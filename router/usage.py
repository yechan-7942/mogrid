import json
import os
import sys
from datetime import date, datetime

from colors import yellow

# provider별 실제 잔여 할당량을 조회하는 공식 API가 없는 provider가 대부분이라(무료
# 티어), mogrid를 통해 실제로 호출한 횟수를 로컬에 누적 기록하는 방식으로 대신한다.
# 세션(agent_loop/session.py)과 달리 프로젝트별로 나누지 않는다 — API 사용량은
# provider 쪽에서 프로젝트 구분 없이 하나로 집계되기 때문에, 기록도 전역 하나로 둔다.
USAGE_FILE = os.path.expanduser("~/.mogrid/usage.json")


class UsageError(Exception):
    pass


def _today() -> str:
    return date.today().isoformat()


def _empty_record() -> dict:
    return {
        "total_success": 0,
        "total_fail": 0,
        "today_date": _today(),
        "today_success": 0,
        "today_fail": 0,
        "last_used": None,
        "last_error": None,
    }


def load_usage(path: str | None = None) -> dict:
    path = path or USAGE_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise UsageError(f"사용량 파일을 읽는 중 오류가 발생했습니다: {path} ({e})")
    except json.JSONDecodeError as e:
        raise UsageError(f"사용량 파일이 손상되었습니다: {path} ({e})")
    if not isinstance(data, dict):
        raise UsageError(f"사용량 파일 형식이 올바르지 않습니다 (dict가 아님): {path}")
    return data


def save_usage(data: dict, path: str | None = None) -> None:
    make_parent = path is None
    path = path or USAGE_FILE
    try:
        if make_parent:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise UsageError(f"사용량 파일을 저장하는 중 오류가 발생했습니다: {path} ({e})")


def _roll_today(record: dict) -> dict:
    # 날짜가 바뀌었으면 "오늘" 집계만 리셋한다. 전체 누적(total_*)은 그대로 둔다.
    if record.get("today_date") != _today():
        record["today_date"] = _today()
        record["today_success"] = 0
        record["today_fail"] = 0
    return record


def _record(provider: str, *, success: bool, error_text: str | None) -> None:
    try:
        data = load_usage()
    except UsageError as e:
        print(yellow(f"[경고] 사용량 파일을 읽지 못해 새로 시작합니다: {e}"), file=sys.stderr)
        data = {}

    record = _roll_today(data.get(provider) or _empty_record())
    if success:
        record["total_success"] += 1
        record["today_success"] += 1
        record["last_used"] = datetime.now().isoformat(timespec="seconds")
    else:
        record["total_fail"] += 1
        record["today_fail"] += 1
        record["last_error"] = error_text
    data[provider] = record

    # 기록 실패는 실제 작업(LLM 호출)을 막을 이유가 없는 부가 기능이므로, 예외를
    # 올리지 않고 경고만 남긴다 — 다만 silent fail은 안 되니 화면에는 띄운다.
    try:
        save_usage(data)
    except UsageError as e:
        print(yellow(f"[경고] 사용량 기록을 저장하지 못했습니다: {e}"), file=sys.stderr)


def record_success(provider: str) -> None:
    _record(provider, success=True, error_text=None)


def record_failure(provider: str, error_text: str) -> None:
    _record(provider, success=False, error_text=error_text)
