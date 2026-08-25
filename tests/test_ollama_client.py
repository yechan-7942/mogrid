import unittest
from unittest.mock import patch

import requests

from router.ollama_client import OllamaError, call_ollama
from tests.helpers import FakeResponse


class CallOllamaTests(unittest.TestCase):
    @patch("router.ollama_client.requests.post")
    def test_success_returns_content(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"choices": [{"message": {"content": "안녕하세요"}}]}
        )
        self.assertEqual(call_ollama("안녕"), "안녕하세요")

    @patch("router.ollama_client.requests.post")
    def test_sends_think_false_to_avoid_leaking_reasoning_into_content(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"choices": [{"message": {"content": "안녕하세요"}}]}
        )
        call_ollama("안녕")
        sent_payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_payload["think"], False)

    @patch("router.ollama_client.requests.post")
    def test_empty_content_raises_ollama_error(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"choices": [{"message": {"content": ""}}]})
        with self.assertRaises(OllamaError):
            call_ollama("안녕")

    @patch("router.ollama_client.requests.post")
    def test_connection_error_raises_ollama_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError()
        with self.assertRaises(OllamaError):
            call_ollama("안녕")

    @patch("router.ollama_client.requests.post")
    def test_timeout_raises_ollama_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        with self.assertRaises(OllamaError):
            call_ollama("안녕")

    @patch("router.ollama_client.requests.post")
    def test_404_raises_ollama_error(self, mock_post):
        mock_post.return_value = FakeResponse(404, text="model not found")
        with self.assertRaises(OllamaError):
            call_ollama("안녕")

    @patch("router.ollama_client.requests.post")
    def test_500_raises_ollama_error(self, mock_post):
        mock_post.return_value = FakeResponse(500, text="server error")
        with self.assertRaises(OllamaError):
            call_ollama("안녕")

    @patch("router.ollama_client.requests.post")
    def test_malformed_body_raises_ollama_error(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"unexpected": "shape"})
        with self.assertRaises(OllamaError):
            call_ollama("안녕")


if __name__ == "__main__":
    unittest.main()
