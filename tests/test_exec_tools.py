import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.exec_tools import PROJECT_ROOT_ENV, run_command
from tools.file_tools import ToolError


class ExecToolsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name
        self._env_patch = patch.dict(os.environ, {PROJECT_ROOT_ENV: self.tmp})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self._tmpdir.cleanup()


class RunCommandTests(ExecToolsTestCase):
    def test_empty_command_raises(self):
        with self.assertRaises(ToolError):
            run_command("")

    def test_disallowed_command_raises(self):
        with self.assertRaises(ToolError):
            run_command("rm -rf /")

    def test_runs_allowed_command_and_captures_stdout(self):
        result = run_command("python3 -c \"print('hi')\"")
        self.assertIn("hi", result)
        self.assertIn("exit code: 0", result)

    def test_nonzero_exit_code_reported(self):
        result = run_command("python3 -c \"import sys; sys.exit(1)\"")
        self.assertIn("exit code: 1", result)

    def test_cwd_outside_project_root_raises(self):
        with self.assertRaises(ToolError):
            run_command("git status", cwd="..")

    def test_nonexistent_cwd_raises(self):
        with self.assertRaises(ToolError):
            run_command("git status", cwd="no-such-dir")

    def test_unparsable_command_raises(self):
        with self.assertRaises(ToolError):
            run_command('git status "unterminated')

    @patch("tools.exec_tools.subprocess.run")
    def test_timeout_raises_tool_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="npm install", timeout=60)
        with self.assertRaises(ToolError):
            run_command("npm install")

    @patch("tools.exec_tools.subprocess.run")
    def test_command_not_found_raises_tool_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(ToolError):
            run_command("git status")

    @patch("tools.exec_tools.subprocess.run")
    def test_long_output_is_truncated(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["npm", "install"], returncode=0, stdout="x" * 5000, stderr=""
        )
        result = run_command("npm install")
        self.assertIn("생략됨", result)
        self.assertLess(len(result), 5000)


if __name__ == "__main__":
    unittest.main()
