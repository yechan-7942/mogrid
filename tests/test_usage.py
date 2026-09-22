import json
import os
import tempfile
import unittest
from unittest.mock import patch

from router.usage import (
    UsageError,
    load_usage,
    record_failure,
    record_success,
    save_usage,
)


class UsageTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.usage_path = os.path.join(self._tmpdir.name, "usage.json")

    def tearDown(self):
        self._tmpdir.cleanup()


class LoadUsageTests(UsageTestCase):
    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(load_usage(self.usage_path), {})

    def test_loads_saved_data(self):
        save_usage({"groq": {"total_success": 1}}, self.usage_path)
        self.assertEqual(load_usage(self.usage_path), {"groq": {"total_success": 1}})

    def test_corrupted_json_raises_usage_error(self):
        with open(self.usage_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        with self.assertRaises(UsageError):
            load_usage(self.usage_path)

    def test_non_dict_content_raises_usage_error(self):
        with open(self.usage_path, "w", encoding="utf-8") as f:
            f.write("[1, 2, 3]")
        with self.assertRaises(UsageError):
            load_usage(self.usage_path)


class SaveUsageTests(UsageTestCase):
    def test_overwrites_previous_content(self):
        save_usage({"groq": {"total_success": 1}}, self.usage_path)
        save_usage({"groq": {"total_success": 2}}, self.usage_path)
        self.assertEqual(load_usage(self.usage_path), {"groq": {"total_success": 2}})

    def test_unwritable_path_raises_usage_error(self):
        bad_path = os.path.join(self._tmpdir.name, "no-such-dir", "usage.json")
        with self.assertRaises(UsageError):
            save_usage({"groq": {}}, bad_path)


class RecordSuccessAndFailureTests(UsageTestCase):
    def setUp(self):
        super().setUp()
        self._patch = patch("router.usage.USAGE_FILE", self.usage_path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        super().tearDown()

    def test_record_success_increments_total_and_today(self):
        record_success("groq")
        data = load_usage(self.usage_path)
        self.assertEqual(data["groq"]["total_success"], 1)
        self.assertEqual(data["groq"]["today_success"], 1)
        self.assertIsNotNone(data["groq"]["last_used"])

    def test_record_failure_increments_total_and_today_and_stores_error(self):
        record_failure("groq", "일부러 실패")
        data = load_usage(self.usage_path)
        self.assertEqual(data["groq"]["total_fail"], 1)
        self.assertEqual(data["groq"]["today_fail"], 1)
        self.assertEqual(data["groq"]["last_error"], "일부러 실패")

    def test_multiple_calls_accumulate_for_same_provider(self):
        record_success("groq")
        record_success("groq")
        record_failure("groq", "실패")
        data = load_usage(self.usage_path)
        self.assertEqual(data["groq"]["total_success"], 2)
        self.assertEqual(data["groq"]["total_fail"], 1)

    def test_different_providers_tracked_separately(self):
        record_success("groq")
        record_success("gemini")
        record_success("gemini")
        data = load_usage(self.usage_path)
        self.assertEqual(data["groq"]["total_success"], 1)
        self.assertEqual(data["gemini"]["total_success"], 2)

    def test_today_counters_reset_when_date_changes(self):
        with open(self.usage_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "groq": {
                        "total_success": 5,
                        "total_fail": 0,
                        "today_date": "2000-01-01",
                        "today_success": 5,
                        "today_fail": 0,
                        "last_used": "2000-01-01T00:00:00",
                        "last_error": None,
                    }
                },
                f,
            )
        record_success("groq")
        data = load_usage(self.usage_path)
        self.assertEqual(data["groq"]["today_success"], 1)
        self.assertEqual(data["groq"]["total_success"], 6)

    def test_corrupted_file_is_recovered_from_on_record(self):
        with open(self.usage_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        record_success("groq")  # 예외 없이 새로 시작해야 한다
        data = load_usage(self.usage_path)
        self.assertEqual(data["groq"]["total_success"], 1)


if __name__ == "__main__":
    unittest.main()
