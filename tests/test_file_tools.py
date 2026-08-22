import os
import tempfile
import unittest
from unittest.mock import patch

from tools.file_tools import (
    ToolError,
    append_file,
    list_files,
    make_dir,
    read_file,
    search_files,
    write_file,
)
from tools.sandbox import PROJECT_ROOT_ENV


class FileToolsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name
        self._env_patch = patch.dict(os.environ, {PROJECT_ROOT_ENV: self.tmp})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self._tmpdir.cleanup()

    def path(self, *parts: str) -> str:
        return os.path.join(self.tmp, *parts)


class ListFilesTests(FileToolsTestCase):
    def test_empty_directory(self):
        self.assertEqual(list_files(self.tmp), "(빈 디렉터리)")

    def test_lists_entries_sorted(self):
        open(self.path("b.txt"), "w").close()
        open(self.path("a.txt"), "w").close()
        self.assertEqual(list_files(self.tmp), "a.txt\nb.txt")

    def test_nonexistent_path_raises(self):
        with self.assertRaises(ToolError):
            list_files(self.path("does-not-exist"))

    def test_file_path_raises_not_a_directory(self):
        file_path = self.path("f.txt")
        open(file_path, "w").close()
        with self.assertRaises(ToolError):
            list_files(file_path)


class ReadFileTests(FileToolsTestCase):
    def test_reads_existing_file(self):
        file_path = self.path("f.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("내용")
        self.assertEqual(read_file(file_path), "내용")

    def test_missing_file_raises(self):
        with self.assertRaises(ToolError):
            read_file(self.path("no-such-file.txt"))

    def test_directory_path_raises(self):
        with self.assertRaises(ToolError):
            read_file(self.tmp)


class WriteFileTests(FileToolsTestCase):
    def test_creates_new_file(self):
        file_path = self.path("new.txt")
        write_file(file_path, "hello")
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello")

    def test_overwrites_existing_content(self):
        file_path = self.path("f.txt")
        write_file(file_path, "old")
        write_file(file_path, "new")
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new")

    def test_returns_length_message(self):
        file_path = self.path("f.txt")
        result = write_file(file_path, "12345")
        self.assertIn("5", result)


class AppendFileTests(FileToolsTestCase):
    def test_appends_to_existing_file(self):
        file_path = self.path("f.txt")
        write_file(file_path, "first")
        append_file(file_path, "second")
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "firstsecond")

    def test_creates_file_if_missing(self):
        file_path = self.path("new.txt")
        append_file(file_path, "content")
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "content")


class MakeDirTests(FileToolsTestCase):
    def test_creates_nested_directories(self):
        target = self.path("a", "b", "c")
        make_dir(target)
        self.assertTrue(os.path.isdir(target))

    def test_idempotent_on_existing_directory(self):
        target = self.path("a")
        make_dir(target)
        make_dir(target)  # 두 번째 호출도 에러 없이 통과해야 함
        self.assertTrue(os.path.isdir(target))


class SearchFilesTests(FileToolsTestCase):
    def test_empty_keyword_raises(self):
        with self.assertRaises(ToolError):
            search_files("", self.tmp)

    def test_nonexistent_path_raises(self):
        with self.assertRaises(ToolError):
            search_files("keyword", self.path("does-not-exist"))

    def test_matches_by_filename(self):
        open(self.path("report.txt"), "w").close()
        result = search_files("report", self.tmp)
        self.assertIn("report.txt", result)
        self.assertIn("파일명 일치", result)

    def test_matches_by_content(self):
        file_path = self.path("notes.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("여기 keyword가 있다\n")
        result = search_files("keyword", self.tmp)
        self.assertIn("notes.txt", result)

    def test_no_match_returns_message(self):
        open(self.path("f.txt"), "w").close()
        result = search_files("존재안함", self.tmp)
        self.assertIn("검색 결과가 없습니다", result)

    def test_skips_hidden_and_skip_dirs(self):
        skip_dir = self.path("__pycache__")
        hidden_dir = self.path(".git")
        os.makedirs(skip_dir)
        os.makedirs(hidden_dir)
        open(os.path.join(skip_dir, "match.txt"), "w").close()
        open(os.path.join(hidden_dir, "match.txt"), "w").close()
        result = search_files("match", self.tmp)
        self.assertIn("검색 결과가 없습니다", result)


class SandboxScopingTests(FileToolsTestCase):
    def test_relative_path_resolves_inside_project_root(self):
        write_file("relative.txt", "hi")
        with open(self.path("relative.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hi")

    def test_write_file_outside_project_root_raises(self):
        with self.assertRaises(ToolError):
            write_file("../escape.txt", "hi")

    def test_read_file_outside_project_root_raises(self):
        with self.assertRaises(ToolError):
            read_file("../../etc/hosts")

    def test_list_files_outside_project_root_raises(self):
        with self.assertRaises(ToolError):
            list_files("..")

    def test_make_dir_outside_project_root_raises(self):
        with self.assertRaises(ToolError):
            make_dir("../escape-dir")

    def test_search_files_outside_project_root_raises(self):
        with self.assertRaises(ToolError):
            search_files("keyword", "..")


if __name__ == "__main__":
    unittest.main()
