import unittest
from unittest.mock import patch

from agent_loop.session import PROMPT_OLDER_ENTRY_CHARS
from agent_loop.summarizer import SUMMARY_PREFIX, SUMMARY_TARGET_CHARS, summarize_entries


class SummarizeEntriesTests(unittest.TestCase):
    @patch("agent_loop.summarizer.call_llm")
    def test_returns_llm_output(self, mock_call_llm):
        mock_call_llm.return_value = "요약된 내용"
        self.assertEqual(summarize_entries(["작업: a\n결과: 1"]), "요약된 내용")

    @patch("agent_loop.summarizer.call_llm")
    def test_prompt_includes_all_entries(self, mock_call_llm):
        mock_call_llm.return_value = "요약"
        summarize_entries(["작업: a\n결과: 1", "작업: b\n결과: 2"])
        prompt = mock_call_llm.call_args.args[0]
        self.assertIn("작업: a", prompt)
        self.assertIn("작업: b", prompt)

    @patch("agent_loop.summarizer.call_llm")
    def test_prompt_asks_for_length_that_survives_prompt_cap(self, mock_call_llm):
        mock_call_llm.return_value = "요약"
        summarize_entries(["작업: a\n결과: 1"])
        self.assertIn(f"{SUMMARY_TARGET_CHARS}자 이내", mock_call_llm.call_args.args[0])

    def test_target_length_fits_inside_older_entry_cap(self):
        # 요약 항목은 세션 맨 앞(오래된 자리)에 들어가므로 PROMPT_OLDER_ENTRY_CHARS로 잘린다.
        self.assertLessEqual(
            SUMMARY_TARGET_CHARS + len(SUMMARY_PREFIX), PROMPT_OLDER_ENTRY_CHARS
        )


if __name__ == "__main__":
    unittest.main()
