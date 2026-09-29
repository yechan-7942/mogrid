import unittest

from agent_loop.text_utils import cap_entries


class CapEntriesTests(unittest.TestCase):
    def test_keeps_only_the_most_recent_entries(self):
        self.assertEqual(cap_entries(["a", "b", "c"], 2, 100), ["b", "c"])

    def test_truncates_entries_over_the_limit(self):
        [result] = cap_entries(["x" * 50], 10, 10)
        self.assertTrue(result.startswith("x" * 10))
        self.assertIn("생략됨", result)

    def test_short_entries_are_left_alone(self):
        self.assertEqual(cap_entries(["짧음"], 10, 100), ["짧음"])


class CapEntriesTaperTests(unittest.TestCase):
    """오래된 항목만 더 강하게 줄이는 동작 — 매 스텝 재전송되는 프롬프트 크기를
    줄이되, 모델이 실제로 보고 행동하는 최근 항목은 온전히 남기기 위한 것."""

    def test_recent_entries_keep_the_larger_limit(self):
        entries = ["x" * 100 for _ in range(5)]
        result = cap_entries(entries, 5, 80, older_max_chars=10, recent_count=2)
        # 최근 2개는 80자 상한
        self.assertTrue(result[-1].startswith("x" * 80))
        self.assertTrue(result[-2].startswith("x" * 80))

    def test_older_entries_are_cut_harder(self):
        entries = ["x" * 100 for _ in range(5)]
        result = cap_entries(entries, 5, 80, older_max_chars=10, recent_count=2)
        for entry in result[:3]:
            self.assertTrue(entry.startswith("x" * 10))
            self.assertLess(len(entry), 30)

    def test_without_older_limit_behaviour_is_unchanged(self):
        entries = ["x" * 100 for _ in range(3)]
        self.assertEqual(
            cap_entries(entries, 3, 20),
            cap_entries(entries, 3, 20, older_max_chars=None, recent_count=2),
        )

    def test_recent_count_larger_than_history_keeps_everything_full(self):
        # 스텝이 얼마 안 쌓였을 때 오래된 항목 취급으로 잘리면 안 된다
        entries = ["x" * 100, "y" * 100]
        result = cap_entries(entries, 15, 80, older_max_chars=10, recent_count=3)
        for entry in result:
            self.assertGreater(len(entry), 50)

    def test_recent_count_zero_cuts_everything_to_the_lower_limit(self):
        entries = ["x" * 100 for _ in range(3)]
        result = cap_entries(entries, 3, 80, older_max_chars=10, recent_count=0)
        for entry in result:
            self.assertTrue(entry.startswith("x" * 10))
            self.assertLess(len(entry), 30)


if __name__ == "__main__":
    unittest.main()
