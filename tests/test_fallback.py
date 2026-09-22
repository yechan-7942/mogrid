import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from router import fallback
from router.fallback import AllProvidersFailedError, call_llm


class FakeProviderError(Exception):
    pass


class OtherFakeProviderError(Exception):
    pass


def _ok(prompt: str) -> str:
    return f"ok: {prompt}"


def _fail(prompt: str) -> str:
    raise FakeProviderError("일부러 실패")


class UsageIsolatedTestCase(unittest.TestCase):
    """call_llm()이 record_success/record_failure로 실제 ~/.mogrid/usage.json을
    건드리지 않도록, 매 테스트를 임시 파일로 격리한다."""

    def setUp(self):
        self._usage_tmpdir = tempfile.TemporaryDirectory()
        self._usage_patch = patch(
            "router.usage.USAGE_FILE", os.path.join(self._usage_tmpdir.name, "usage.json")
        )
        self._usage_patch.start()

    def tearDown(self):
        self._usage_patch.stop()
        self._usage_tmpdir.cleanup()


class CallLlmTests(UsageIsolatedTestCase):
    def setUp(self):
        super().setUp()
        fallback._reset_rotation()

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

    @patch(
        "router.fallback.PROVIDERS",
        [("fake1", _fail, FakeProviderError), ("fake2", _ok, OtherFakeProviderError)],
    )
    def test_long_error_message_is_truncated_on_screen_but_not_in_failure_detail(self):
        long_message = "x" * 5000

        def _fail_long(prompt: str) -> str:
            raise FakeProviderError(long_message)

        with patch("router.fallback.PROVIDERS", [("fake1", _fail_long, FakeProviderError), ("fake2", _ok, OtherFakeProviderError)]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                call_llm("안녕")
        printed = buf.getvalue()
        # 화면에는 잘려서 나가야 한다 (reasoning 모델의 raw 응답 덤프로 터미널이
        # 도배되는 걸 막기 위한 변경)
        self.assertNotIn(long_message, printed)
        self.assertIn("생략", printed)

    @patch(
        "router.fallback.PROVIDERS",
        [("fake1", _fail, FakeProviderError), ("fake2", _fail, FakeProviderError)],
    )
    def test_all_failing_keeps_full_untruncated_detail_in_exception(self):
        long_message = "y" * 5000

        def _fail_long(prompt: str) -> str:
            raise FakeProviderError(long_message)

        with patch(
            "router.fallback.PROVIDERS",
            [("fake1", _fail_long, FakeProviderError), ("fake2", _fail_long, FakeProviderError)],
        ):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(AllProvidersFailedError) as ctx:
                    call_llm("안녕")
        # 전부 실패했을 때 던지는 예외에는 잘리지 않은 전체 메시지가 남아있어야
        # 나중에 진짜 원인을 디버깅할 수 있다.
        self.assertIn(long_message, str(ctx.exception))

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


class RotationTests(UsageIsolatedTestCase):
    def setUp(self):
        super().setUp()
        fallback._reset_rotation()

    def tearDown(self):
        fallback._reset_rotation()
        super().tearDown()

    def test_starting_provider_rotates_across_calls(self):
        calls = []

        def make_fn(name):
            def fn(prompt: str) -> str:
                calls.append(name)
                return f"{name}-ok"

            return fn

        providers = [
            ("p1", make_fn("p1"), FakeProviderError),
            ("p2", make_fn("p2"), FakeProviderError),
            ("p3", make_fn("p3"), FakeProviderError),
        ]
        with patch("router.fallback.PROVIDERS", providers):
            for _ in range(4):
                call_llm("안녕")

        self.assertEqual(calls, ["p1", "p2", "p3", "p1"])

    def test_rotation_still_wraps_around_to_earlier_providers_on_failure(self):
        calls = []

        def tracked_fail(name):
            def fn(prompt: str) -> str:
                calls.append(name)
                raise FakeProviderError("일부러 실패")

            return fn

        def tracked_ok(name):
            def fn(prompt: str) -> str:
                calls.append(name)
                return f"{name}-ok"

            return fn

        providers = [
            ("p1", tracked_ok("p1"), FakeProviderError),
            ("p2", tracked_fail("p2"), FakeProviderError),
            ("p3", tracked_fail("p3"), FakeProviderError),
        ]
        with patch("router.fallback.PROVIDERS", providers):
            fallback._rotation = 1  # start=p2 이번 호출부터
            result = call_llm("안녕")

        # p2(fail) -> p3(fail) -> 앞으로 돌아가 p1(성공) 순서로 전부 시도돼야 한다
        self.assertEqual(calls, ["p2", "p3", "p1"])
        self.assertEqual(result, "p1-ok")


if __name__ == "__main__":
    unittest.main()
