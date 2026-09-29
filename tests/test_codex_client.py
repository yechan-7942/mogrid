import subprocess
import unittest
from unittest.mock import patch

from router.codex_client import CodexError, call_codex


def _fake_run(returncode=0, last_message="안녕하세요", stderr=""):
    """codex는 최종 응답을 stdout이 아니라 `-o` 파일에 쓰므로, 가짜 실행도 그 파일을
    만들어줘야 실제 동작과 같아진다."""

    def run(cmd, **kwargs):
        if returncode == 0:
            out_path = cmd[cmd.index("-o") + 1]
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(last_message)
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    return run


class CallCodexTests(unittest.TestCase):
    @patch("router.codex_client.subprocess.run")
    def test_success_returns_last_message(self, mock_run):
        mock_run.side_effect = _fake_run()
        self.assertEqual(call_codex("안녕"), "안녕하세요")

    @patch("router.codex_client.subprocess.run")
    def test_prompt_goes_through_stdin_not_argv(self, mock_run):
        mock_run.side_effect = _fake_run()
        long_prompt = "x" * 500_000
        call_codex(long_prompt)
        # argv로 넘기면 ARG_MAX에 걸리므로 프롬프트 자리는 `-`여야 하고 본문은 stdin
        self.assertEqual(mock_run.call_args.args[0][-1], "-")
        self.assertEqual(mock_run.call_args.kwargs["input"], long_prompt)

    @patch("router.codex_client.subprocess.run")
    def test_runs_read_only_outside_user_repo(self, mock_run):
        mock_run.side_effect = _fake_run()
        call_codex("안녕")
        cmd = mock_run.call_args.args[0]
        # codex는 파일을 고치는 에이전트라 순수 생성기로 묶어두는 게 안전 요건이다
        self.assertEqual(cmd[cmd.index("-s") + 1], "read-only")
        workdir = cmd[cmd.index("-C") + 1]
        self.assertNotIn("danger-full-access", cmd)
        self.assertTrue(workdir.startswith("/"))

    @patch("router.codex_client.subprocess.run")
    def test_missing_cli_raises_codex_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(CodexError):
            call_codex("안녕")

    @patch("router.codex_client.subprocess.run")
    def test_timeout_raises_codex_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=180)
        with self.assertRaises(CodexError):
            call_codex("안녕")

    @patch("router.codex_client.subprocess.run")
    def test_nonzero_exit_includes_stderr_detail(self, mock_run):
        mock_run.side_effect = _fake_run(returncode=1, stderr="usage limit reached")
        with self.assertRaises(CodexError) as ctx:
            call_codex("안녕")
        self.assertIn("usage limit reached", str(ctx.exception))

    @patch("router.codex_client.subprocess.run")
    def test_empty_response_raises_codex_error(self, mock_run):
        mock_run.side_effect = _fake_run(last_message="   ")
        with self.assertRaises(CodexError):
            call_codex("안녕")


if __name__ == "__main__":
    unittest.main()
