import json

from router.fallback import call_llm
from tools.registry import TOOL_SCHEMAS, ToolError, call_tool

MAX_STEPS = 6


class AgentLoopError(Exception):
    pass


def build_system_prompt() -> str:
    tools_desc = "\n".join(
        f"- {t['name']}({', '.join(t['args'].keys())}): {t['description']}"
        for t in TOOL_SCHEMAS
    )
    return (
        "너는 파일을 읽고 쓰며 작업을 수행하는 에이전트다.\n"
        "다음 tool들을 사용할 수 있다:\n"
        f"{tools_desc}\n\n"
        "규칙:\n"
        "- 파일 경로를 확실히 모르면 절대 추측하지 말고, "
        "list_files(path='.')로 현재 위치부터 확인해라.\n"
        "- 작업 설명에 등장하는 프로젝트/폴더 이름을 실제 경로의 일부라고 가정하지 마라.\n"
        "- 같은 경로가 이미 실패했다면 그 경로를 다시 시도하지 말고, "
        "지금까지의 기록을 참고해 다른 경로를 시도해라.\n\n"
        "매 턴마다 반드시 아래 두 형식 중 하나로만, JSON 객체 하나만 응답해라. "
        "설명이나 다른 텍스트를 절대 덧붙이지 마라.\n"
        '1) tool 호출: {"tool": "<tool 이름>", "args": {...}}\n'
        '2) 최종 답변: {"final": "<최종 답변>"}\n'
    )


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AgentLoopError(f"모델 응답에서 JSON을 찾을 수 없습니다: {text}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise AgentLoopError(f"모델 응답 JSON 파싱 실패: {e} / raw={text}")


def run_agent(task: str, max_steps: int = MAX_STEPS) -> str:
    system_prompt = build_system_prompt()
    history = []

    for step in range(1, max_steps + 1):
        history_text = "\n".join(history) if history else "(없음)"
        prompt = (
            f"{system_prompt}\n"
            f"작업: {task}\n\n"
            f"지금까지 기록:\n{history_text}\n\n"
            "다음 행동을 JSON으로 응답해라."
        )

        raw_response = call_llm(prompt)
        parsed = extract_json(raw_response)

        if "final" in parsed:
            return parsed["final"]

        if "tool" in parsed:
            tool_name = parsed["tool"]
            tool_args = parsed.get("args", {})
            print(f"[agent_loop] step {step}: {tool_name}({tool_args}) 호출")
            try:
                result = call_tool(tool_name, tool_args)
            except ToolError as e:
                result = f"에러: {e}"
            history.append(f"[{step}] tool={tool_name} args={tool_args} -> {result}")
            continue

        raise AgentLoopError(f"모델 응답에 'tool'도 'final'도 없습니다: {parsed}")

    raise AgentLoopError(f"{max_steps}스텝 안에 최종 답변을 받지 못했습니다.")


if __name__ == "__main__":
    result = run_agent("mogrid 프로젝트의 CLAUDE.md 파일 내용을 읽어서 한 문장으로 요약해줘.")
    print("=== 최종 결과 ===")
    print(result)
