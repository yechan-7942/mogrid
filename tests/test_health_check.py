import unittest
from unittest.mock import patch

import requests

from router.health_check import (
    check_gemini,
    check_groq,
    check_mistral,
    check_nvidia,
    check_ollama,
    check_openrouter,
    run_all_checks,
)
from tests.helpers import FakeResponse


class CheckGroqTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_is_skipped(self):
        provider, status, detail = check_groq()
        self.assertEqual(provider, "Groq")
        self.assertEqual(status, "skipped")

    @patch.dict("os.environ", {"GROQ_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_default_model_present_is_ok(self, mock_get):
        from router.groq_client import DEFAULT_MODEL

        mock_get.return_value = FakeResponse(200, {"data": [{"id": DEFAULT_MODEL}]})
        provider, status, detail = check_groq()
        self.assertEqual(status, "ok")

    @patch.dict("os.environ", {"GROQ_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_default_model_absent_is_missing(self, mock_get):
        mock_get.return_value = FakeResponse(200, {"data": [{"id": "other-model"}]})
        provider, status, detail = check_groq()
        self.assertEqual(status, "missing")

    @patch.dict("os.environ", {"GROQ_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_error_status_code_is_error(self, mock_get):
        mock_get.return_value = FakeResponse(401, text="unauthorized")
        provider, status, detail = check_groq()
        self.assertEqual(status, "error")

    @patch.dict("os.environ", {"GROQ_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_network_failure_is_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        provider, status, detail = check_groq()
        self.assertEqual(status, "error")

    @patch.dict("os.environ", {"GROQ_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_unexpected_shape_is_error(self, mock_get):
        mock_get.return_value = FakeResponse(200, {"unexpected": "shape"})
        provider, status, detail = check_groq()
        self.assertEqual(status, "error")


class CheckMistralTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_is_skipped(self):
        self.assertEqual(check_mistral()[1], "skipped")

    @patch.dict("os.environ", {"MISTRAL_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_default_model_present_is_ok(self, mock_get):
        from router.mistral_client import DEFAULT_MODEL

        mock_get.return_value = FakeResponse(200, {"data": [{"id": DEFAULT_MODEL}]})
        self.assertEqual(check_mistral()[1], "ok")


class CheckNvidiaTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_is_skipped(self):
        self.assertEqual(check_nvidia()[1], "skipped")

    @patch.dict("os.environ", {"NVIDIA_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_default_model_present_is_ok(self, mock_get):
        from router.nvidia_client import DEFAULT_MODEL

        mock_get.return_value = FakeResponse(200, {"data": [{"id": DEFAULT_MODEL}]})
        self.assertEqual(check_nvidia()[1], "ok")


class CheckOpenRouterTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch("router.health_check.requests.get")
    def test_works_without_api_key(self, mock_get):
        from router.openrouter_client import DEFAULT_MODEL

        mock_get.return_value = FakeResponse(200, {"data": [{"id": DEFAULT_MODEL}]})
        provider, status, detail = check_openrouter()
        self.assertEqual(status, "ok")
        self.assertEqual(mock_get.call_args.kwargs["headers"], {})

    @patch.dict("os.environ", {}, clear=True)
    @patch("router.health_check.requests.get")
    def test_default_model_absent_is_missing(self, mock_get):
        mock_get.return_value = FakeResponse(200, {"data": [{"id": "other-model"}]})
        self.assertEqual(check_openrouter()[1], "missing")


class CheckGeminiTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_is_skipped(self):
        self.assertEqual(check_gemini()[1], "skipped")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_default_model_present_is_ok(self, mock_get):
        from router.gemini_client import DEFAULT_MODEL

        mock_get.return_value = FakeResponse(
            200, {"models": [{"name": f"models/{DEFAULT_MODEL}"}]}
        )
        self.assertEqual(check_gemini()[1], "ok")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "k"})
    @patch("router.health_check.requests.get")
    def test_default_model_absent_is_missing(self, mock_get):
        mock_get.return_value = FakeResponse(200, {"models": [{"name": "models/other"}]})
        self.assertEqual(check_gemini()[1], "missing")


class CheckOllamaTests(unittest.TestCase):
    @patch("router.health_check.requests.get")
    def test_default_model_present_is_ok(self, mock_get):
        from router.ollama_client import DEFAULT_MODEL

        mock_get.return_value = FakeResponse(200, {"models": [{"name": DEFAULT_MODEL}]})
        self.assertEqual(check_ollama()[1], "ok")

    @patch("router.health_check.requests.get")
    def test_default_model_absent_is_missing(self, mock_get):
        mock_get.return_value = FakeResponse(200, {"models": [{"name": "other"}]})
        self.assertEqual(check_ollama()[1], "missing")

    @patch("router.health_check.requests.get")
    def test_connection_error_is_skipped_not_error(self, mock_get):
        # 로컬 Ollama 서버가 아예 안 떠 있는 건 "고장"이 아니라 그냥 미사용 상태다.
        mock_get.side_effect = requests.exceptions.ConnectionError()
        self.assertEqual(check_ollama()[1], "skipped")


class RunAllChecksTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch("router.health_check.requests.get")
    def test_returns_one_result_per_provider(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        results = run_all_checks()
        providers = [r[0] for r in results]
        self.assertEqual(
            providers, ["Groq", "Gemini", "OpenRouter", "Mistral", "NVIDIA NIM", "Ollama"]
        )


if __name__ == "__main__":
    unittest.main()
