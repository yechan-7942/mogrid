import json
import os
import tempfile
import unittest
from unittest.mock import patch

import agent_loop.session as session_module
from agent_loop.session import (
    MAX_ENTRY_CHARS,
    MAX_SESSION_ENTRIES,
    PROMPT_MAX_ENTRY_CHARS,
    PROMPT_OLDER_ENTRY_CHARS,
    PROMPT_RECENT_ENTRIES,
    SessionError,
    load_session,
    save_session,
    session_file_path,
    session_prompt_entries,
    trim_session,
)
from tools.sandbox import PROJECT_ROOT_ENV


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


class SessionPromptEntriesTests(unittest.TestCase):
    def test_prompt_cap_is_tighter_than_disk_cap(self):
        self.assertLess(PROMPT_MAX_ENTRY_CHARS, MAX_ENTRY_CHARS)
        self.assertLess(PROMPT_OLDER_ENTRY_CHARS, PROMPT_MAX_ENTRY_CHARS)

    def test_short_entries_unchanged(self):
        entries = ["a", "b", "c"]
        self.assertEqual(session_prompt_entries(entries), entries)

    def test_recent_entries_keep_larger_cap(self):
        entries = ["x" * 5000 for _ in range(MAX_SESSION_ENTRIES)]
        capped = session_prompt_entries(entries)
        for entry in capped[-PROMPT_RECENT_ENTRIES:]:
            self.assertTrue(entry.startswith("x" * PROMPT_MAX_ENTRY_CHARS))

    def test_older_entries_get_smaller_cap(self):
        entries = ["x" * 5000 for _ in range(MAX_SESSION_ENTRIES)]
        capped = session_prompt_entries(entries)
        for entry in capped[:-PROMPT_RECENT_ENTRIES]:
            self.assertLessEqual(len(entry), PROMPT_OLDER_ENTRY_CHARS + len(" …(생략됨)"))
            self.assertTrue(entry.startswith("x" * PROMPT_OLDER_ENTRY_CHARS))

    def test_does_not_mutate_input(self):
        entries = ["x" * 5000 for _ in range(MAX_SESSION_ENTRIES)]
        session_prompt_entries(entries)
        self.assertTrue(all(len(entry) == 5000 for entry in entries))

    def test_prompt_block_is_much_smaller_than_disk_block(self):
        entries = ["x" * MAX_ENTRY_CHARS for _ in range(MAX_SESSION_ENTRIES)]
        disk_block = "\n\n".join(trim_session(entries))
        prompt_block = "\n\n".join(session_prompt_entries(entries))
        self.assertLess(len(prompt_block), len(disk_block) // 2)


class LoadSessionSelfHealsOversizedFileTests(SessionTestCase):
    def test_load_trims_legacy_oversized_file(self):
        entries = [f"entry-{i}" for i in range(MAX_SESSION_ENTRIES + 5)]
        with open(self.session_path, "w", encoding="utf-8") as f:
            json.dump(entries, f)  # save_session을 거치지 않은, 트리밍 전 레거시 파일 흉내
        self.assertEqual(load_session(self.session_path), entries[-MAX_SESSION_ENTRIES:])


class SessionFilePathScopingTests(unittest.TestCase):
    def setUp(self):
        self._session_dir_tmp = tempfile.TemporaryDirectory()
        self._project_tmp = tempfile.TemporaryDirectory()
        self._session_dir_patch = patch.object(
            session_module, "SESSION_DIR", self._session_dir_tmp.name
        )
        self._session_dir_patch.start()

    def tearDown(self):
        self._session_dir_patch.stop()
        self._session_dir_tmp.cleanup()
        self._project_tmp.cleanup()

    def test_different_project_roots_get_different_session_files(self):
        with patch.dict(os.environ, {PROJECT_ROOT_ENV: "/tmp/project-a"}):
            path_a = session_file_path()
        with patch.dict(os.environ, {PROJECT_ROOT_ENV: "/tmp/project-b"}):
            path_b = session_file_path()
        self.assertNotEqual(path_a, path_b)

    def test_same_project_root_gets_same_session_file(self):
        with patch.dict(os.environ, {PROJECT_ROOT_ENV: "/tmp/project-a"}):
            self.assertEqual(session_file_path(), session_file_path())

    def test_default_save_and_load_round_trip_via_project_root(self):
        with patch.dict(os.environ, {PROJECT_ROOT_ENV: self._project_tmp.name}):
            save_session(["작업: 테스트\n결과: 완료"])
            self.assertEqual(load_session(), ["작업: 테스트\n결과: 완료"])

    def test_default_save_does_not_touch_project_root_directory(self):
        with patch.dict(os.environ, {PROJECT_ROOT_ENV: self._project_tmp.name}):
            save_session(["x"])
        self.assertEqual(os.listdir(self._project_tmp.name), [])


if __name__ == "__main__":
    unittest.main()
