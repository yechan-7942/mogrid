import os
import re
import unittest
from unittest.mock import patch

from banner import (
    _abbreviate_home,
    _configured_provider_count,
    _display_width,
    _pad,
    _truncate,
    render_welcome_banner,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class DisplayWidthTests(unittest.TestCase):
    def test_ascii_is_width_one_per_char(self):
        self.assertEqual(_display_width("abc"), 3)

    def test_korean_is_width_two_per_char(self):
        self.assertEqual(_display_width("가나"), 4)

    def test_mixed_text(self):
        self.assertEqual(_display_width("a가b"), 4)


class PadTests(unittest.TestCase):
    def test_pads_with_spaces_to_target_width(self):
        self.assertEqual(_pad("ab", 5), "ab   ")

    def test_accounts_for_wide_chars_when_padding(self):
        self.assertEqual(_display_width(_pad("가", 5)), 5)

    def test_no_padding_when_already_at_width(self):
        self.assertEqual(_pad("abcde", 5), "abcde")


class TruncateTests(unittest.TestCase):
    def test_short_text_is_unchanged(self):
        self.assertEqual(_truncate("abc", 10), "abc")

    def test_long_text_is_truncated_with_ellipsis(self):
        result = _truncate("abcdefghij", 5)
        self.assertLessEqual(_display_width(result), 5)
        self.assertTrue(result.endswith("…"))


class AbbreviateHomeTests(unittest.TestCase):
    def test_home_prefix_is_replaced_with_tilde(self):
        home = os.path.expanduser("~")
        self.assertEqual(_abbreviate_home(f"{home}/project"), "~/project")

    def test_non_home_path_is_unchanged(self):
        self.assertEqual(_abbreviate_home("/var/tmp/x"), "/var/tmp/x")


class ConfiguredProviderCountTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_keys_still_counts_ollama(self):
        self.assertEqual(_configured_provider_count(), 1)

    @patch.dict(
        os.environ,
        {"GROQ_API_KEY": "k", "GEMINI_API_KEY": "k", "MISTRAL_API_KEY": "k"},
        clear=True,
    )
    def test_counts_configured_keys_plus_ollama(self):
        self.assertEqual(_configured_provider_count(), 4)


class RenderWelcomeBannerTests(unittest.TestCase):
    def test_every_line_has_equal_display_width(self):
        lines = [_strip_ansi(line) for line in render_welcome_banner().split("\n")]
        widths = {_display_width(line) for line in lines}
        self.assertEqual(len(widths), 1, f"줄마다 폭이 달라 테두리가 어긋남: {lines}")

    def test_box_borders_match(self):
        lines = [_strip_ansi(line) for line in render_welcome_banner().split("\n")]
        self.assertTrue(lines[0].startswith("╭") and lines[0].endswith("╮"))
        self.assertTrue(lines[-1].startswith("╰") and lines[-1].endswith("╯"))
        for line in lines[1:-1]:
            self.assertTrue(line.startswith("│") and line.endswith("│"))

    def test_includes_greeting_with_given_user(self):
        text = _strip_ansi(render_welcome_banner(user="테스트유저"))
        self.assertIn("테스트유저", text)

    def test_includes_setup_and_check_models_tips(self):
        text = _strip_ansi(render_welcome_banner())
        self.assertIn("mogrid setup", text)
        self.assertIn("mogrid check-models", text)


if __name__ == "__main__":
    unittest.main()
