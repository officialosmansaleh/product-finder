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


class PublicCatalogAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_env = {k: os.environ.get(k) for k in [
            "AUTH_DB_PATH",
            "AUTH_DATABASE_URL",
            "AUTH_JWT_SECRET",
            "ADMIN_BOOTSTRAP_EMAIL",
            "ADMIN_BOOTSTRAP_PASSWORD",
            "ADMIN_BOOTSTRAP_NAME",
        ]}
        cls._tmpdir = tempfile.TemporaryDirectory()
        os.environ["AUTH_DB_PATH"] = os.path.join(cls._tmpdir.name, "auth.db")
        os.environ["AUTH_DATABASE_URL"] = ""
        os.environ["AUTH_JWT_SECRET"] = "test-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
        os.environ["ADMIN_BOOTSTRAP_EMAIL"] = "admin@test.local"
        os.environ["ADMIN_BOOTSTRAP_PASSWORD"] = "AdminPass1234"
        os.environ["ADMIN_BOOTSTRAP_NAME"] = "Test Admin"

        try:
            from fastapi.testclient import TestClient
            main = importlib.import_module("app.main")
            main = importlib.reload(main)
        except Exception as e:  # pragma: no cover - env-dependent
            raise unittest.SkipTest(f"Skipping public catalog access test (import/setup failed): {e}")

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

    def test_anonymous_search_is_available_without_ai(self):
        response = self.client.post(
            "/search",
            json={
                "text": "downlight",
                "filters": {},
                "limit": 5,
                "include_similar": True,
                "allow_ai": False,
                "debug": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("exact", data)
        self.assertGreater(len(data["exact"]), 0)

    def test_anonymous_facets_are_available_without_ai(self):
        response = self.client.post(
            "/facets",
            json={
                "text": "",
                "filters": {},
                "allow_ai": False,
                "debug": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("families", data)
        self.assertGreater(len(data["families"]), 0)
        self.assertIn("product_name_short", data)

    def test_admin_routes_still_require_authentication(self):
        response = self.client.get("/admin/users/pending")
        self.assertEqual(response.status_code, 401, response.text)

    def test_debug_endpoints_are_disabled_by_default(self):
        response = self.client.get("/debug/parse", params={"q": "office downlight"})
        self.assertEqual(response.status_code, 404, response.text)

    def test_database_admin_routes_are_not_public(self):
        response = self.client.post("/database/refresh")
        self.assertEqual(response.status_code, 401, response.text)
        response = self.client.post("/database/recreate")
        self.assertEqual(response.status_code, 401, response.text)

    def test_admin_access_matrix_requires_authentication(self):
        response = self.client.get("/admin/access-matrix")
        self.assertEqual(response.status_code, 401, response.text)


if __name__ == "__main__":
    unittest.main()
