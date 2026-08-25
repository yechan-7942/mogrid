import os
import tempfile
import unittest
from unittest.mock import patch

from tools.file_tools import ToolError
from tools.registry import TOOL_SCHEMAS, TOOLS, call_tool
from tools.sandbox import PROJECT_ROOT_ENV
from tools.task_tracker import render_task_list, reset_tasks


class RegistryConsistencyTests(unittest.TestCase):
    def test_every_schema_has_matching_tool_function(self):
        schema_names = {schema["name"] for schema in TOOL_SCHEMAS}
        self.assertEqual(schema_names, set(TOOLS.keys()))


class CallToolTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name
        self._env_patch = patch.dict(os.environ, {PROJECT_ROOT_ENV: self.tmp})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self._tmpdir.cleanup()

    def test_unknown_tool_raises(self):
        with self.assertRaises(ToolError):
            call_tool("does_not_exist", {})

    def test_dispatches_to_write_file(self):
        file_path = os.path.join(self.tmp, "f.txt")
        call_tool("write_file", {"path": file_path, "content": "hi"})
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hi")

    def test_dispatches_to_list_files(self):
        result = call_tool("list_files", {"path": self.tmp})
        self.assertEqual(result, "(빈 디렉터리)")

    def test_missing_required_arg_raises_tool_error(self):
        with self.assertRaises(ToolError):
            call_tool("write_file", {"path": os.path.join(self.tmp, "f.txt")})

    def test_unexpected_arg_raises_tool_error(self):
        with self.assertRaises(ToolError):
            call_tool("list_files", {"path": self.tmp, "bogus": 1})

    def test_dispatches_to_edit_file(self):
        file_path = os.path.join(self.tmp, "f.txt")
        call_tool("write_file", {"path": file_path, "content": "hello world"})
        call_tool("edit_file", {"path": file_path, "old_string": "world", "new_string": "there"})
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello there")

    def test_dispatches_to_update_task_list(self):
        self.addCleanup(reset_tasks)
        call_tool("update_task_list", {"tasks": [{"content": "a", "status": "pending"}]})
        self.assertIn("a", render_task_list())


if __name__ == "__main__":
    unittest.main()
