import unittest
from unittest.mock import patch

import requests

from router.mistral_client import MistralError, call_mistral
from tests.helpers import FakeResponse


@patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key"})
class CallMistralTests(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(MistralError):
                call_mistral("안녕")

    @patch("router.mistral_client.requests.post")
    def test_success_returns_content(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"choices": [{"message": {"content": "안녕하세요"}}]}
        )
        self.assertEqual(call_mistral("안녕"), "안녕하세요")

    @patch("router.mistral_client.requests.post")
    def test_empty_content_raises_mistral_error(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"choices": [{"message": {"content": ""}}]}
        )
        with self.assertRaises(MistralError):
            call_mistral("안녕")

    @patch("router.mistral_client.requests.post")
    def test_timeout_raises_mistral_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        with self.assertRaises(MistralError):
            call_mistral("안녕")

    @patch("router.mistral_client.requests.post")
    def test_connection_error_raises_mistral_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError()
        with self.assertRaises(MistralError):
            call_mistral("안녕")

    @patch("router.mistral_client.requests.post")
    def test_401_raises_mistral_error(self, mock_post):
        mock_post.return_value = FakeResponse(401, text="unauthorized")
        with self.assertRaises(MistralError):
            call_mistral("안녕")

    @patch("router.mistral_client.requests.post")
    def test_429_raises_mistral_error(self, mock_post):
        mock_post.return_value = FakeResponse(429, text="rate limited")
        with self.assertRaises(MistralError):
            call_mistral("안녕")

    @patch("router.mistral_client.requests.post")
    def test_server_error_raises_mistral_error(self, mock_post):
        mock_post.return_value = FakeResponse(500, text="boom")
        with self.assertRaises(MistralError):
            call_mistral("안녕")

    @patch("router.mistral_client.requests.post")
    def test_malformed_body_raises_mistral_error(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"unexpected": "shape"})
        with self.assertRaises(MistralError):
            call_mistral("안녕")


if __name__ == "__main__":
    unittest.main()
