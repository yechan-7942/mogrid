import os
import tempfile
import unittest

from agent_loop.session import SessionError, load_session, save_session


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


if __name__ == "__main__":
    unittest.main()
