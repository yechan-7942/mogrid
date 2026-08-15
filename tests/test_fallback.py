import unittest
from unittest.mock import patch

from router.fallback import AllProvidersFailedError, call_llm


class FakeProviderError(Exception):
    pass


class OtherFakeProviderError(Exception):
    pass


def _ok(prompt: str) -> str:
    return f"ok: {prompt}"


def _fail(prompt: str) -> str:
    raise FakeProviderError("일부러 실패")


class CallLlmTests(unittest.TestCase):
    @patch(
        "router.fallback.PROVIDERS",
        [("fake", _ok, FakeProviderError)],
    )
    def test_first_provider_success_returns_immediately(self):
        self.assertEqual(call_llm("안녕"), "ok: 안녕")

    @patch(
        "router.fallback.PROVIDERS",
        [("fake1", _fail, FakeProviderError), ("fake2", _ok, OtherFakeProviderError)],
    )
    def test_falls_back_to_next_provider_on_failure(self):
        self.assertEqual(call_llm("안녕"), "ok: 안녕")

    @patch(
        "router.fallback.PROVIDERS",
        [("fake1", _fail, FakeProviderError), ("fake2", _fail, FakeProviderError)],
    )
    def test_all_providers_failing_raises_all_providers_failed(self):
        with self.assertRaises(AllProvidersFailedError) as ctx:
            call_llm("안녕")
        self.assertIn("fake1", str(ctx.exception))
        self.assertIn("fake2", str(ctx.exception))

    def test_second_provider_not_called_when_first_succeeds(self):
        second_calls = []

        def tracked_ok(prompt: str) -> str:
            second_calls.append(prompt)
            return "ok"

        with patch(
            "router.fallback.PROVIDERS",
            [("fake1", _ok, FakeProviderError), ("fake2", tracked_ok, OtherFakeProviderError)],
        ):
            call_llm("안녕")
        self.assertEqual(second_calls, [])


if __name__ == "__main__":
    unittest.main()
