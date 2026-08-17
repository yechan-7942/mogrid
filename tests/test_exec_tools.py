import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import exec_tools
from tools.exec_tools import (
    PROJECT_ROOT_ENV,
    check_process,
    kill_all_processes,
    run_command,
    start_process,
    stop_process,
)
from tools.file_tools import ToolError


class ExecToolsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name
        self._env_patch = patch.dict(os.environ, {PROJECT_ROOT_ENV: self.tmp})
        self._env_patch.start()

    def tearDown(self):
        kill_all_processes()  # 테스트가 중간에 실패해도 백그라운드 프로세스/로그 파일이 안 남게
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


class StartProcessTests(ExecToolsTestCase):
    def setUp(self):
        super().setUp()
        # 실제로 1초씩 기다리면 테스트가 느려지니 시작 유예 시간을 짧게 줄인다.
        self._grace_patch = patch("tools.exec_tools.STARTUP_GRACE_SECONDS", 0.05)
        self._grace_patch.start()

    def tearDown(self):
        self._grace_patch.stop()
        super().tearDown()

    @staticmethod
    def _extract_process_id(start_result: str) -> str:
        return start_result.split("process_id=")[1].split(" ")[0]

    def test_disallowed_command_raises(self):
        with self.assertRaises(ToolError):
            start_process("bash -c 'sleep 5'")

    def test_long_running_process_reports_started(self):
        result = start_process("python3 -c \"import time; time.sleep(5)\"")
        self.assertIn("백그라운드 실행 시작됨", result)

    def test_immediately_exiting_process_reports_exit_code_and_output(self):
        result = start_process("python3 -u -c \"print('bye'); import sys; sys.exit(3)\"")
        self.assertIn("바로 종료됨", result)
        self.assertIn("exit code: 3", result)
        self.assertIn("bye", result)

    def test_check_process_reports_running_then_unknown_after_stop(self):
        start_result = start_process("python3 -c \"import time; time.sleep(5)\"")
        process_id = self._extract_process_id(start_result)

        status = check_process(process_id)
        self.assertIn("실행 중", status)

        stop_process(process_id)
        with self.assertRaises(ToolError):
            check_process(process_id)

    def test_check_process_unknown_id_raises(self):
        with self.assertRaises(ToolError):
            check_process("no-such-id")

    def test_stop_process_terminates_running_process(self):
        start_result = start_process("python3 -c \"import time; time.sleep(5)\"")
        process_id = self._extract_process_id(start_result)

        stop_result = stop_process(process_id)
        self.assertIn("종료 완료", stop_result)

    def test_stop_process_unknown_id_raises(self):
        with self.assertRaises(ToolError):
            stop_process("no-such-id")

    def test_kill_all_processes_cleans_up_tracked_processes(self):
        start_process("python3 -c \"import time; time.sleep(5)\"")
        start_process("python3 -c \"import time; time.sleep(5)\"")
        self.assertEqual(len(exec_tools._PROCESSES), 2)

        kill_all_processes()

        self.assertEqual(len(exec_tools._PROCESSES), 0)


if __name__ == "__main__":
    unittest.main()
