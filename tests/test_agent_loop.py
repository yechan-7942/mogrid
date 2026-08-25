import json
import os
import tempfile
import unittest
from unittest.mock import patch

from agent_loop.loop import AgentLoopError, extract_json, requires_confirmation, run_agent
from router.fallback import AllProvidersFailedError
from tools.registry import ToolError
from tools.sandbox import PROJECT_ROOT_ENV
from tools.task_tracker import render_task_list


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

    def test_ignores_trailing_content_after_valid_json(self):
        # Qwen 같은 hybrid-thinking 모델이 JSON 뒤에 </think> 태그나 JSON을 한 번 더
        # 붙여서 반환하는 경우 (실사용 중 재현됨) — 첫 번째 완전한 JSON만 뽑아야 한다.
        text = '{"tool": "list_files", "args": {"path": "."}}\n</think>\n\n{"tool": "list_files", "args": {"path": "."}}'
        self.assertEqual(
            extract_json(text), {"tool": "list_files", "args": {"path": "."}}
        )

    def test_ignores_duplicate_trailing_brace(self):
        text = '{"tool": "read_file", "args": {"path": "calc.py"}}}'
        self.assertEqual(
            extract_json(text), {"tool": "read_file", "args": {"path": "calc.py"}}
        )


class RequiresConfirmationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._env_patch = patch.dict(os.environ, {PROJECT_ROOT_ENV: self._tmpdir.name})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self._tmpdir.cleanup()

    def test_run_command_always_requires_confirmation(self):
        reason = requires_confirmation("run_command", {"command": "git push"})
        self.assertIsNotNone(reason)
        self.assertIn("git push", reason)

    def test_write_file_to_new_path_does_not_require_confirmation(self):
        self.assertIsNone(
            requires_confirmation("write_file", {"path": "new.txt", "content": "x"})
        )

    def test_write_file_overwriting_existing_file_requires_confirmation(self):
        existing = os.path.join(self._tmpdir.name, "existing.txt")
        open(existing, "w").close()
        reason = requires_confirmation("write_file", {"path": "existing.txt", "content": "x"})
        self.assertIsNotNone(reason)

    def test_write_file_outside_sandbox_does_not_require_confirmation(self):
        # call_tool 단계에서 어차피 ToolError로 막히므로 확인 단계에서는 그냥 통과시킨다.
        self.assertIsNone(
            requires_confirmation("write_file", {"path": "../escape.txt", "content": "x"})
        )

    def test_other_tools_do_not_require_confirmation(self):
        safe_tools = [
            "edit_file", "append_file", "make_dir", "read_file", "list_files",
            "search_files", "update_task_list", "start_process", "check_process",
            "stop_process",
        ]
        for name in safe_tools:
            self.assertIsNone(requires_confirmation(name, {}))


class RunAgentConfirmationGatingTests(unittest.TestCase):
    @patch("agent_loop.loop.call_tool")
    @patch("agent_loop.loop.call_llm")
    def test_denied_confirmation_blocks_tool_and_is_reported_in_history(
        self, mock_call_llm, mock_call_tool
    ):
        mock_call_llm.side_effect = [
            json.dumps({"tool": "run_command", "args": {"command": "git push"}}),
            json.dumps({"final": "취소됨"}),
        ]
        result = run_agent("작업", confirm=lambda reason: False)
        self.assertEqual(result, "취소됨")
        mock_call_tool.assert_not_called()
        second_prompt = mock_call_llm.call_args_list[1].args[0]
        self.assertIn("승인하지 않아", second_prompt)

    @patch("agent_loop.loop.call_tool")
    @patch("agent_loop.loop.call_llm")
    def test_approved_confirmation_proceeds_with_tool_call(self, mock_call_llm, mock_call_tool):
        mock_call_llm.side_effect = [
            json.dumps({"tool": "run_command", "args": {"command": "git status"}}),
            json.dumps({"final": "완료"}),
        ]
        mock_call_tool.return_value = "ok"
        result = run_agent("작업", confirm=lambda reason: True)
        self.assertEqual(result, "완료")
        mock_call_tool.assert_called_once_with("run_command", {"command": "git status"})

    @patch("agent_loop.loop.call_tool")
    @patch("agent_loop.loop.call_llm")
    def test_no_confirm_callback_means_no_gating(self, mock_call_llm, mock_call_tool):
        mock_call_llm.side_effect = [
            json.dumps({"tool": "run_command", "args": {"command": "git status"}}),
            json.dumps({"final": "완료"}),
        ]
        mock_call_tool.return_value = "ok"
        result = run_agent("작업")
        self.assertEqual(result, "완료")
        mock_call_tool.assert_called_once()


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
    def test_response_without_tool_or_final_is_recoverable(self, mock_call_llm):
        mock_call_llm.side_effect = [
            json.dumps({"unexpected": "shape"}),
            json.dumps({"final": "복구됨"}),
        ]
        result = run_agent("아무 작업")
        self.assertEqual(result, "복구됨")
        second_prompt = mock_call_llm.call_args_list[1].args[0]
        self.assertIn("에러", second_prompt)

    @patch("agent_loop.loop.call_llm")
    def test_persistent_missing_tool_or_final_eventually_raises(self, mock_call_llm):
        mock_call_llm.return_value = json.dumps({"unexpected": "shape"})
        with self.assertRaises(AgentLoopError):
            run_agent("아무 작업", max_steps=2)
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch("agent_loop.loop.call_llm")
    def test_malformed_json_response_is_recoverable(self, mock_call_llm):
        mock_call_llm.side_effect = [
            "이건 JSON이 아니라 그냥 텍스트",
            json.dumps({"final": "복구됨"}),
        ]
        result = run_agent("아무 작업")
        self.assertEqual(result, "복구됨")
        second_prompt = mock_call_llm.call_args_list[1].args[0]
        self.assertIn("올바른 JSON이 아니었다", second_prompt)

    @patch("agent_loop.loop.call_llm")
    def test_persistent_malformed_json_eventually_raises(self, mock_call_llm):
        mock_call_llm.return_value = "계속 JSON이 아님"
        with self.assertRaises(AgentLoopError):
            run_agent("아무 작업", max_steps=2)
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch("agent_loop.loop.call_llm")
    def test_task_list_rendered_into_next_prompt(self, mock_call_llm):
        mock_call_llm.side_effect = [
            json.dumps(
                {
                    "tool": "update_task_list",
                    "args": {"tasks": [{"content": "첫 하위 작업", "status": "in_progress"}]},
                }
            ),
            json.dumps({"final": "완료"}),
        ]

        run_agent("여러 단계짜리 작업")

        second_prompt = mock_call_llm.call_args_list[1].args[0]
        self.assertIn("첫 하위 작업", second_prompt)

    @patch("agent_loop.loop.call_llm")
    def test_task_list_reset_between_separate_runs(self, mock_call_llm):
        from tools.task_tracker import update_task_list

        update_task_list([{"content": "이전 작업 잔재", "status": "pending"}])
        mock_call_llm.return_value = json.dumps({"final": "완료"})

        run_agent("새 작업")

        self.assertNotIn("이전 작업 잔재", render_task_list())

    @patch("agent_loop.loop.call_llm")
    def test_all_providers_failed_raises_agent_loop_error_immediately(self, mock_call_llm):
        # 모든 provider가 실패하면 재시도해도 나아질 여지가 없으므로, history에 남겨
        # 스텝을 반복하지 말고 즉시 AgentLoopError로 보고해야 한다 (main.py가 잡을 수 있게).
        mock_call_llm.side_effect = AllProvidersFailedError("모든 provider가 실패했습니다.")
        with self.assertRaises(AgentLoopError):
            run_agent("아무 작업", max_steps=10)
        self.assertEqual(mock_call_llm.call_count, 1)

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
