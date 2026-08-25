import unittest
from unittest.mock import patch

from agent_loop.summarizer import summarize_entries


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


if __name__ == "__main__":
    unittest.main()
