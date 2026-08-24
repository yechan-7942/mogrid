import unittest
from unittest.mock import patch

import requests

from router.nvidia_client import NvidiaError, call_nvidia
from tests.helpers import FakeResponse


@patch.dict("os.environ", {"NVIDIA_API_KEY": "test-key"})
class CallNvidiaTests(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(NvidiaError):
                call_nvidia("안녕")

    @patch("router.nvidia_client.requests.post")
    def test_success_returns_content(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"choices": [{"message": {"content": "안녕하세요"}}]}
        )
        self.assertEqual(call_nvidia("안녕"), "안녕하세요")

    @patch("router.nvidia_client.requests.post")
    def test_null_content_raises_nvidia_error(self, mock_post):
        # reasoning 모델이 content 대신 reasoning 필드에만 답을 넣는 회귀 케이스
        mock_post.return_value = FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {"content": None, "reasoning": "생각만 하고 답은 안 함"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )
        with self.assertRaises(NvidiaError):
            call_nvidia("안녕")

    @patch("router.nvidia_client.requests.post")
    def test_empty_string_content_raises_nvidia_error(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"choices": [{"message": {"content": ""}}]})
        with self.assertRaises(NvidiaError):
            call_nvidia("안녕")

    @patch("router.nvidia_client.requests.post")
    def test_timeout_raises_nvidia_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        with self.assertRaises(NvidiaError):
            call_nvidia("안녕")

    @patch("router.nvidia_client.requests.post")
    def test_401_raises_nvidia_error(self, mock_post):
        mock_post.return_value = FakeResponse(401, text="unauthorized")
        with self.assertRaises(NvidiaError):
            call_nvidia("안녕")

    @patch("router.nvidia_client.requests.post")
    def test_429_raises_nvidia_error(self, mock_post):
        mock_post.return_value = FakeResponse(429, text="rate limited")
        with self.assertRaises(NvidiaError):
            call_nvidia("안녕")

    @patch("router.nvidia_client.requests.post")
    def test_malformed_body_raises_nvidia_error(self, mock_post):
        mock_post.return_value = FakeResponse(200, {"unexpected": "shape"})
        with self.assertRaises(NvidiaError):
            call_nvidia("안녕")


if __name__ == "__main__":
    unittest.main()
