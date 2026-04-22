import importlib
import os
import shutil
import sys
import tempfile
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class AIFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_env = {k: os.environ.get(k) for k in [
            "AUTH_DB_PATH",
            "AUTH_DATABASE_URL",
            "AUTH_JWT_SECRET",
            "ADMIN_BOOTSTRAP_EMAIL",
            "ADMIN_BOOTSTRAP_PASSWORD",
            "ADMIN_BOOTSTRAP_NAME",
            "OPENAI_API_KEY",
        ]}
        cls._tmpdir = tempfile.TemporaryDirectory()
        os.environ["AUTH_DB_PATH"] = os.path.join(cls._tmpdir.name, "auth.db")
        os.environ["AUTH_DATABASE_URL"] = ""
        os.environ["AUTH_JWT_SECRET"] = "test-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
        os.environ["ADMIN_BOOTSTRAP_EMAIL"] = "admin@test.local"
        os.environ["ADMIN_BOOTSTRAP_PASSWORD"] = "AdminPass1234"
        os.environ["ADMIN_BOOTSTRAP_NAME"] = "Test Admin"
        os.environ["OPENAI_API_KEY"] = ""

        try:
            from fastapi.testclient import TestClient
            import app.ai_service as ai_service
            ai_service = importlib.reload(ai_service)
            import app.llm_intent as llm_intent
            llm_intent = importlib.reload(llm_intent)
            main = importlib.import_module("app.main")
            main = importlib.reload(main)
        except Exception as exc:  # pragma: no cover - env-dependent
            raise unittest.SkipTest(f"Skipping AI fallback test (import/setup failed): {exc}")

        cls.ai_service = ai_service
        cls.client_cm = TestClient(main.app)
        cls.client = cls.client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)
        for key, value in cls._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            cls._tmpdir.cleanup()
        except PermissionError:
            shutil.rmtree(cls._tmpdir.name, ignore_errors=True)

    def test_ai_service_reports_disabled_when_api_key_is_missing(self):
        result = self.ai_service._request_json_completion(
            messages=[{"role": "user", "content": "office downlight dali"}],
            response_model=type("TmpModel", (), {"model_validate": staticmethod(lambda v: v)}),  # pragma: no cover - never reached
            model_candidates=("gpt-4.1-mini",),
        )
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(result["content"], {})
        self.assertIn("missing", result["message"].lower())

    def test_search_gracefully_degrades_when_ai_is_unavailable(self):
        response = self.client.post(
            "/search",
            json={"text": "office downlight dali 4000k", "filters": {}, "allow_ai": True, "limit": 5},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        interpreted = payload.get("interpreted") or {}
        self.assertEqual(interpreted.get("ai_status"), "disabled")
        self.assertIn("OpenAI", str(interpreted.get("ai_note") or ""))


if __name__ == "__main__":
    unittest.main()
