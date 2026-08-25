import os
import tempfile
import unittest
from unittest.mock import patch

from agent_loop.session import MAX_SESSION_ENTRIES
from agent_loop.summarizer import SUMMARY_PREFIX
from main import (
    PROVIDER_SETUP,
    interactive_confirm,
    one_shot_confirm,
    run_setup,
    summarize_session_if_needed,
)
from router.fallback import AllProvidersFailedError


class RunSetupTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.env_path = os.path.join(self._tmpdir.name, ".env")
        open(self.env_path, "a", encoding="utf-8").close()

        self._find_dotenv_patch = patch("main.find_dotenv", return_value=self.env_path)
        self._find_dotenv_patch.start()
        self._load_dotenv_patch = patch("main.load_dotenv")
        self._load_dotenv_patch.start()
        self._webbrowser_patch = patch("main.webbrowser.open", return_value=True)
        self.mock_webbrowser = self._webbrowser_patch.start()

        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        for env_var, _, _ in PROVIDER_SETUP:
            os.environ.pop(env_var, None)

    def tearDown(self):
        self._find_dotenv_patch.stop()
        self._load_dotenv_patch.stop()
        self._webbrowser_patch.stop()
        self._env_patch.stop()
        self._tmpdir.cleanup()

    @patch("main.set_key")
    @patch("main.getpass", return_value="")
    @patch("main.input", return_value="")
    def test_blank_input_skips_every_provider(self, mock_input, mock_getpass, mock_set_key):
        run_setup()
        mock_set_key.assert_not_called()

    @patch("main.set_key")
    @patch("main.getpass")
    @patch("main.input", return_value="")
    def test_saves_key_when_provided(self, mock_input, mock_getpass, mock_set_key):
        mock_getpass.side_effect = ["key-groq", "", "", "", ""]
        run_setup()
        mock_set_key.assert_called_once_with(self.env_path, "GROQ_API_KEY", "key-groq")
        self.assertEqual(os.environ["GROQ_API_KEY"], "key-groq")

    @patch("main.set_key")
    @patch("main.getpass", return_value="")
    @patch("main.input", return_value="")
    def test_does_not_ask_to_overwrite_when_key_absent(self, mock_input, mock_getpass, mock_set_key):
        run_setup()
        mock_input.assert_not_called()

    @patch("main.set_key")
    @patch("main.getpass", return_value="")
    @patch("main.input", return_value="n")
    def test_declining_overwrite_skips_provider(self, mock_input, mock_getpass, mock_set_key):
        os.environ["GROQ_API_KEY"] = "existing"
        run_setup()
        mock_set_key.assert_not_called()
        self.assertEqual(mock_getpass.call_count, len(PROVIDER_SETUP) - 1)

    @patch("main.set_key")
    @patch("main.getpass", return_value="new-key")
    @patch("main.input", return_value="y")
    def test_confirming_overwrite_replaces_key(self, mock_input, mock_getpass, mock_set_key):
        os.environ["GROQ_API_KEY"] = "existing"
        run_setup()
        mock_set_key.assert_any_call(self.env_path, "GROQ_API_KEY", "new-key")

    @patch("main.set_key")
    @patch("main.getpass", return_value="")
    @patch("main.input", return_value="")
    def test_opens_browser_for_every_provider_url(self, mock_input, mock_getpass, mock_set_key):
        run_setup()
        expected_urls = [url for _, _, url in PROVIDER_SETUP]
        actual_urls = [c.args[0] for c in self.mock_webbrowser.call_args_list]
        self.assertEqual(actual_urls, expected_urls)

    @patch("main.set_key")
    @patch("main.getpass", return_value="key-value")
    @patch("main.input", return_value="")
    def test_saved_key_never_printed_to_stdout(self, mock_input, mock_getpass, mock_set_key):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            run_setup()
        self.assertNotIn("key-value", buf.getvalue())


class InteractiveConfirmTests(unittest.TestCase):
    @patch("main.input", return_value="y")
    def test_yes_returns_true(self, mock_input):
        self.assertTrue(interactive_confirm("위험한 작업"))

    @patch("main.input", return_value="n")
    def test_no_returns_false(self, mock_input):
        self.assertFalse(interactive_confirm("위험한 작업"))

    @patch("main.input", return_value="")
    def test_blank_returns_false(self, mock_input):
        self.assertFalse(interactive_confirm("위험한 작업"))


class OneShotConfirmTests(unittest.TestCase):
    def test_auto_approve_true_always_allows(self):
        confirm = one_shot_confirm(True)
        self.assertTrue(confirm("위험한 작업"))

    def test_auto_approve_false_always_blocks(self):
        confirm = one_shot_confirm(False)
        self.assertFalse(confirm("위험한 작업"))


class SummarizeSessionIfNeededTests(unittest.TestCase):
    def test_under_cap_returns_unchanged(self):
        entries = [f"entry-{i}" for i in range(MAX_SESSION_ENTRIES - 1)]
        self.assertEqual(summarize_session_if_needed(entries), entries)

    @patch("main.summarize_entries")
    def test_over_cap_summarizes_oldest_and_keeps_recent(self, mock_summarize):
        mock_summarize.return_value = "요약 결과"
        entries = [f"entry-{i}" for i in range(MAX_SESSION_ENTRIES + 1)]

        result = summarize_session_if_needed(entries)

        self.assertEqual(len(result), MAX_SESSION_ENTRIES)
        self.assertEqual(result[0], f"{SUMMARY_PREFIX}요약 결과")
        self.assertEqual(result[1:], entries[-(MAX_SESSION_ENTRIES - 1):])
        # 넘친 만큼(가장 오래된 것들)만 요약 대상으로 넘겼는지 확인
        summarized_entries = mock_summarize.call_args.args[0]
        self.assertEqual(summarized_entries, entries[: -(MAX_SESSION_ENTRIES - 1)])

    @patch("main.summarize_entries")
    def test_summarization_failure_falls_back_to_plain_trim(self, mock_summarize):
        mock_summarize.side_effect = AllProvidersFailedError("모든 provider가 실패했습니다.")
        entries = [f"entry-{i}" for i in range(MAX_SESSION_ENTRIES + 3)]

        result = summarize_session_if_needed(entries)

        self.assertEqual(len(result), MAX_SESSION_ENTRIES)
        self.assertEqual(result, entries[-MAX_SESSION_ENTRIES:])
        for entry in result:
            self.assertFalse(entry.startswith(SUMMARY_PREFIX))


if __name__ == "__main__":
    unittest.main()
