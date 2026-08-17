import json
import unittest
from unittest.mock import patch

from agent_loop.loop import AgentLoopError, extract_json, run_agent
from tools.registry import ToolError


class ExtractJsonTests(unittest.TestCase):
    def test_parses_plain_json(self):
        self.assertEqual(extract_json('{"final": "답"}'), {"final": "답"})

    def test_parses_json_with_surrounding_text(self):
        text = 'here you go: {"tool": "list_files", "args": {}} thanks'
        self.assertEqual(extract_json(text), {"tool": "list_files", "args": {}})

    def test_no_braces_raises(self):
        with self.assertRaises(AgentLoopError):
            extract_json("설명만 있고 JSON은 없음")

    def test_invalid_json_raises(self):
        with self.assertRaises(AgentLoopError):
            extract_json('{"tool": "list_files", "args": }')


class RunAgentTests(unittest.TestCase):
    @patch("agent_loop.loop.call_llm")
    def test_immediate_final_answer(self, mock_call_llm):
        mock_call_llm.return_value = json.dumps({"final": "정답입니다"})
        self.assertEqual(run_agent("아무 작업"), "정답입니다")
        self.assertEqual(mock_call_llm.call_count, 1)

    @patch("agent_loop.loop.call_tool")
    @patch("agent_loop.loop.call_llm")
    def test_tool_call_then_final(self, mock_call_llm, mock_call_tool):
        mock_call_llm.side_effect = [
            json.dumps({"tool": "list_files", "args": {"path": "."}}),
            json.dumps({"final": "완료"}),
        ]
        mock_call_tool.return_value = "a.txt\nb.txt"

        result = run_agent("파일 목록 확인")

        self.assertEqual(result, "완료")
        mock_call_tool.assert_called_once_with("list_files", {"path": "."})
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch("agent_loop.loop.call_tool")
    @patch("agent_loop.loop.call_llm")
    def test_tool_error_is_reported_back_to_model_not_raised(self, mock_call_llm, mock_call_tool):
        mock_call_llm.side_effect = [
            json.dumps({"tool": "read_file", "args": {"path": "no-such.txt"}}),
            json.dumps({"final": "파일이 없다고 확인했습니다"}),
        ]
        mock_call_tool.side_effect = ToolError("파일을 찾을 수 없습니다: no-such.txt")

        result = run_agent("파일 읽기 시도")

        self.assertEqual(result, "파일이 없다고 확인했습니다")
        # 두 번째 프롬프트에 에러 내용이 기록으로 전달됐는지 확인
        second_prompt = mock_call_llm.call_args_list[1].args[0]
        self.assertIn("에러", second_prompt)
        self.assertIn("파일을 찾을 수 없습니다", second_prompt)

    @patch("agent_loop.loop.call_llm")
    def test_exceeds_max_steps_raises(self, mock_call_llm):
        mock_call_llm.return_value = json.dumps({"tool": "list_files", "args": {}})
        with patch("agent_loop.loop.call_tool", return_value="ok"):
            with self.assertRaises(AgentLoopError):
                run_agent("끝나지 않는 작업", max_steps=2)
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch("agent_loop.loop.call_llm")
    def test_response_without_tool_or_final_raises(self, mock_call_llm):
        mock_call_llm.return_value = json.dumps({"unexpected": "shape"})
        with self.assertRaises(AgentLoopError):
            run_agent("아무 작업")

    @patch("agent_loop.loop.call_llm")
    def test_session_history_included_in_prompt(self, mock_call_llm):
        mock_call_llm.return_value = json.dumps({"final": "정답"})
        run_agent("작업", session_history=["작업: 이전 작업\n결과: 이전 결과"])
        prompt = mock_call_llm.call_args.args[0]
        self.assertIn("이전 작업", prompt)
        self.assertIn("이전 결과", prompt)

    @patch("agent_loop.loop.call_tool")
    @patch("agent_loop.loop.call_llm")
    def test_in_task_history_is_capped_to_recent_entries(self, mock_call_llm, mock_call_tool):
        # MAX_STEPS를 올리면서 history도 같이 캡을 씌웠으므로, 오래된 스텝은
        # 프롬프트에서 빠지고 최근 스텝만 남는지 확인한다.
        with patch("agent_loop.loop.MAX_HISTORY_ENTRIES", 2):
            mock_call_llm.side_effect = [
                json.dumps({"tool": "list_files", "args": {"path": "1"}}),
                json.dumps({"tool": "list_files", "args": {"path": "2"}}),
                json.dumps({"tool": "list_files", "args": {"path": "3"}}),
                json.dumps({"final": "완료"}),
            ]
            mock_call_tool.return_value = "ok"

            run_agent("여러 스텝 작업", max_steps=10)

            last_prompt = mock_call_llm.call_args.args[0]
            self.assertNotIn("'path': '1'", last_prompt)
            self.assertIn("'path': '3'", last_prompt)


if __name__ == "__main__":
    unittest.main()
