import unittest
from unittest.mock import patch

import requests

from router.gemini_client import GeminiError, call_gemini
from tests.helpers import FakeResponse


def _model_output_payload(text: str) -> dict:
    return {
        "steps": [
            {"type": "tool_call"},
            {
                "type": "model_output",
                "content": [{"type": "text", "text": text}],
            },
        ]
    }


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
class CallGeminiTests(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(GeminiError):
                call_gemini("안녕")

    @patch("router.gemini_client.requests.post")
    def test_success_returns_joined_text(self, mock_post):
        mock_post.return_value = FakeResponse(200, _model_output_payload("안녕하세요"))
        self.assertEqual(call_gemini("안녕"), "안녕하세요")

    @patch("router.gemini_client.requests.post")
    def test_timeout_raises_gemini_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        with self.assertRaises(GeminiError):
            call_gemini("안녕")

    @patch("router.gemini_client.requests.post")
    def test_400_raises_gemini_error(self, mock_post):
        mock_post.return_value = FakeResponse(400, text="bad request")
        with self.assertRaises(GeminiError):
            call_gemini("안녕")

    @patch("router.gemini_client.requests.post")
    def test_403_raises_gemini_error(self, mock_post):
        mock_post.return_value = FakeResponse(403, text="forbidden")
        with self.assertRaises(GeminiError):
            call_gemini("안녕")

    @patch("router.gemini_client.requests.post")
    def test_429_raises_gemini_error(self, mock_post):
        mock_post.return_value = FakeResponse(429, text="rate limited")
        with self.assertRaises(GeminiError):
            call_gemini("안녕")

    @patch("router.gemini_client.requests.post")
    def test_no_model_output_steps_raises(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"steps": [{"type": "tool_call"}]})
        with self.assertRaises(GeminiError):
            call_gemini("안녕")

    @patch("router.gemini_client.requests.post")
    def test_no_text_content_raises(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"steps": [{"type": "model_output", "content": []}]}
        )
        with self.assertRaises(GeminiError):
            call_gemini("안녕")


if __name__ == "__main__":
    unittest.main()
