import unittest

from tools.file_tools import ToolError
from tools.task_tracker import render_task_list, reset_tasks, update_task_list


class TaskTrackerTestCase(unittest.TestCase):
    def setUp(self):
        reset_tasks()

    def tearDown(self):
        reset_tasks()


class RenderTaskListTests(TaskTrackerTestCase):
    def test_empty_by_default(self):
        self.assertEqual(render_task_list(), "(작업 목록 없음)")

    def test_renders_status_icons(self):
        update_task_list(
            [
                {"content": "첫 번째", "status": "completed"},
                {"content": "두 번째", "status": "in_progress"},
                {"content": "세 번째", "status": "pending"},
            ]
        )
        rendered = render_task_list()
        self.assertIn("[x] 첫 번째", rendered)
        self.assertIn("[~] 두 번째", rendered)
        self.assertIn("[ ] 세 번째", rendered)


class UpdateTaskListTests(TaskTrackerTestCase):
    def test_replaces_entire_list_each_call(self):
        update_task_list([{"content": "a", "status": "pending"}])
        update_task_list([{"content": "b", "status": "pending"}])
        rendered = render_task_list()
        self.assertNotIn("a", rendered)
        self.assertIn("b", rendered)

    def test_non_list_raises(self):
        with self.assertRaises(ToolError):
            update_task_list("not a list")

    def test_missing_content_raises(self):
        with self.assertRaises(ToolError):
            update_task_list([{"status": "pending"}])

    def test_missing_status_raises(self):
        with self.assertRaises(ToolError):
            update_task_list([{"content": "a"}])

    def test_invalid_status_raises(self):
        with self.assertRaises(ToolError):
            update_task_list([{"content": "a", "status": "done"}])

    def test_empty_list_clears_tasks(self):
        update_task_list([{"content": "a", "status": "pending"}])
        update_task_list([])
        self.assertEqual(render_task_list(), "(작업 목록 없음)")


class ResetTasksTests(TaskTrackerTestCase):
    def test_clears_existing_tasks(self):
        update_task_list([{"content": "a", "status": "pending"}])
        reset_tasks()
        self.assertEqual(render_task_list(), "(작업 목록 없음)")


if __name__ == "__main__":
    unittest.main()
