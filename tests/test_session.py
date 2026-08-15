import json
import os
import tempfile
import unittest

from agent_loop.session import (
    MAX_ENTRY_CHARS,
    MAX_SESSION_ENTRIES,
    SessionError,
    load_session,
    save_session,
    trim_session,
)


class SessionTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.session_path = os.path.join(self._tmpdir.name, "session.json")

    def tearDown(self):
        self._tmpdir.cleanup()


class LoadSessionTests(SessionTestCase):
    def test_missing_file_returns_empty_list(self):
        self.assertEqual(load_session(self.session_path), [])

    def test_loads_saved_entries(self):
        save_session(["a", "b"], self.session_path)
        self.assertEqual(load_session(self.session_path), ["a", "b"])

    def test_corrupted_json_raises_session_error(self):
        with open(self.session_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        with self.assertRaises(SessionError):
            load_session(self.session_path)

    def test_non_list_content_raises_session_error(self):
        with open(self.session_path, "w", encoding="utf-8") as f:
            f.write('{"not": "a list"}')
        with self.assertRaises(SessionError):
            load_session(self.session_path)


class SaveSessionTests(SessionTestCase):
    def test_round_trip_preserves_korean_text(self):
        entries = ["작업: 안녕\n결과: 반갑습니다"]
        save_session(entries, self.session_path)
        self.assertEqual(load_session(self.session_path), entries)

    def test_overwrites_previous_content(self):
        save_session(["old"], self.session_path)
        save_session(["new"], self.session_path)
        self.assertEqual(load_session(self.session_path), ["new"])

    def test_unwritable_path_raises_session_error(self):
        bad_path = os.path.join(self._tmpdir.name, "no-such-dir", "session.json")
        with self.assertRaises(SessionError):
            save_session(["x"], bad_path)

    def test_save_caps_entry_count_on_disk(self):
        entries = [f"entry-{i}" for i in range(MAX_SESSION_ENTRIES + 5)]
        save_session(entries, self.session_path)
        with open(self.session_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(len(saved), MAX_SESSION_ENTRIES)
        self.assertEqual(saved, entries[-MAX_SESSION_ENTRIES:])


class TrimSessionTests(unittest.TestCase):
    def test_short_list_unchanged(self):
        entries = ["a", "b", "c"]
        self.assertEqual(trim_session(entries), entries)

    def test_caps_entry_count_keeping_most_recent(self):
        entries = [f"entry-{i}" for i in range(MAX_SESSION_ENTRIES + 3)]
        trimmed = trim_session(entries)
        self.assertEqual(len(trimmed), MAX_SESSION_ENTRIES)
        self.assertEqual(trimmed, entries[-MAX_SESSION_ENTRIES:])

    def test_truncates_overly_long_entry(self):
        long_entry = "x" * (MAX_ENTRY_CHARS + 100)
        trimmed = trim_session([long_entry])
        self.assertLessEqual(len(trimmed[0]), MAX_ENTRY_CHARS + len(" …(생략됨)"))
        self.assertTrue(trimmed[0].startswith("x" * MAX_ENTRY_CHARS))

    def test_leaves_short_entry_untouched(self):
        entry = "짧은 항목"
        self.assertEqual(trim_session([entry]), [entry])


class LoadSessionSelfHealsOversizedFileTests(SessionTestCase):
    def test_load_trims_legacy_oversized_file(self):
        entries = [f"entry-{i}" for i in range(MAX_SESSION_ENTRIES + 5)]
        with open(self.session_path, "w", encoding="utf-8") as f:
            json.dump(entries, f)  # save_session을 거치지 않은, 트리밍 전 레거시 파일 흉내
        self.assertEqual(load_session(self.session_path), entries[-MAX_SESSION_ENTRIES:])


if __name__ == "__main__":
    unittest.main()
