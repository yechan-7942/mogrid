import unittest
from unittest.mock import patch

import requests

from router.nvidia_client import (
    CONNECT_TIMEOUT,
    FALLBACK_MODELS,
    NvidiaAccountError,
    NvidiaError,
    call_nvidia,
)
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


@patch.dict("os.environ", {"NVIDIA_API_KEY": "test-key"})
class CallNvidiaFallbackModelsTests(unittest.TestCase):
    @patch("router.nvidia_client.requests.post")
    def test_falls_back_to_next_model_on_rate_limit(self, mock_post):
        # 첫 번째 모델은 429, 두 번째 모델은 성공 -> 두 번째 모델의 응답을 받아야 한다.
        mock_post.side_effect = [
            FakeResponse(429, text="rate limited"),
            FakeResponse(200, {"choices": [{"message": {"content": "두 번째 모델 응답"}}]}),
        ]
        self.assertEqual(call_nvidia("안녕"), "두 번째 모델 응답")
        self.assertEqual(mock_post.call_count, 2)
        first_call_model = mock_post.call_args_list[0].kwargs["json"]["model"]
        second_call_model = mock_post.call_args_list[1].kwargs["json"]["model"]
        self.assertEqual(first_call_model, FALLBACK_MODELS[0])
        self.assertEqual(second_call_model, FALLBACK_MODELS[1])

    @patch("router.nvidia_client.requests.post")
    def test_stops_immediately_on_account_error(self, mock_post):
        # 401은 모델을 바꿔도 결과가 같으므로, 목록 전체를 소진하지 않고 바로 멈춰야 한다.
        mock_post.return_value = FakeResponse(401, text="unauthorized")
        with self.assertRaises(NvidiaAccountError):
            call_nvidia("안녕")
        self.assertEqual(mock_post.call_count, 1)

    @patch("router.nvidia_client.requests.post")
    def test_exhausts_all_models_before_raising(self, mock_post):
        mock_post.return_value = FakeResponse(429, text="rate limited")
        with self.assertRaises(NvidiaError):
            call_nvidia("안녕")
        self.assertEqual(mock_post.call_count, len(FALLBACK_MODELS))

    @patch("router.nvidia_client.time.monotonic")
    @patch("router.nvidia_client.requests.post")
    def test_stops_when_total_budget_is_exhausted(self, mock_post, mock_clock):
        # 모델 하나가 timeout을 꽉 채우면 나머지를 계속 돌지 않고 멈춰야 한다.
        # (없으면 느린 모델이 겹칠 때 한 스텝이 수 분씩 멈춘다.)
        mock_post.return_value = FakeResponse(429, text="rate limited")
        # 호출할 때마다 시계가 timeout만큼 진행한 것처럼 흉내낸다.
        mock_clock.side_effect = [0, 0, 30, 60, 90, 120, 150, 180]
        with self.assertRaises(NvidiaError) as ctx:
            call_nvidia("안녕", timeout=30)
        self.assertLess(mock_post.call_count, len(FALLBACK_MODELS))
        self.assertIn("예산", str(ctx.exception))

    @patch("router.nvidia_client.requests.post")
    def test_read_timeout_is_paired_with_connect_timeout(self, mock_post):
        # requests의 scalar timeout은 소켓 연산 단위라 총 시간을 보장하지 않는다.
        # (연결, 읽기) 튜플로 넘겨야 연결 단계에서 매달리는 걸 따로 자를 수 있다.
        mock_post.return_value = FakeResponse(
            200, {"choices": [{"message": {"content": "답"}}]}
        )
        call_nvidia("안녕", model="z-ai/glm-5.3", timeout=30)
        self.assertEqual(mock_post.call_args.kwargs["timeout"], (CONNECT_TIMEOUT, 30))

    @patch("router.nvidia_client.requests.post")
    def test_explicit_model_skips_fallback_list(self, mock_post):
        mock_post.return_value = FakeResponse(
            200, {"choices": [{"message": {"content": "지정 모델 응답"}}]}
        )
        self.assertEqual(call_nvidia("안녕", model="openai/gpt-oss-20b"), "지정 모델 응답")
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["model"], "openai/gpt-oss-20b"
        )


if __name__ == "__main__":
    unittest.main()
