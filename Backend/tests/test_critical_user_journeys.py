import importlib
import os
import shutil
import sys
import tempfile
import unittest
import uuid


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class CriticalUserJourneySmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_env = {k: os.environ.get(k) for k in [
            "AUTH_DB_PATH",
            "AUTH_DATABASE_URL",
            "AUTH_JWT_SECRET",
            "ADMIN_BOOTSTRAP_EMAIL",
            "ADMIN_BOOTSTRAP_PASSWORD",
            "ADMIN_BOOTSTRAP_NAME",
            "AUTH_TOKEN_EXPIRE_MINUTES",
            "PF_SKIP_RUNTIME_INIT",
        ]}
        cls._tmpdir = tempfile.TemporaryDirectory()
        os.environ["AUTH_DB_PATH"] = os.path.join(cls._tmpdir.name, "auth.db")
        os.environ["AUTH_DATABASE_URL"] = ""
        os.environ["AUTH_JWT_SECRET"] = "test-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
        os.environ["ADMIN_BOOTSTRAP_EMAIL"] = "admin@test.local"
        os.environ["ADMIN_BOOTSTRAP_PASSWORD"] = "AdminPass1234"
        os.environ["ADMIN_BOOTSTRAP_NAME"] = "Test Admin"
        os.environ["AUTH_TOKEN_EXPIRE_MINUTES"] = "120"
        os.environ["PF_SKIP_RUNTIME_INIT"] = "1"

        try:
            from fastapi.testclient import TestClient
            main = importlib.import_module("app.main")
            main = importlib.reload(main)
        except Exception as e:  # pragma: no cover - env-dependent
            raise unittest.SkipTest(f"Skipping critical journey smoke test (import/setup failed): {e}")

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

    def _login(self, email: str, password: str) -> tuple[str, dict]:
        response = self.client.post("/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        return payload["access_token"], payload

    def _auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _create_and_approve_user(self) -> tuple[str, str]:
        email = f"journey.{uuid.uuid4().hex[:8]}@test.local"
        password = "StrongPass123"
        signup = self.client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": password,
                "full_name": "Journey User",
                "company_name": "Journey Co",
                "country": "Italy",
            },
        )
        self.assertEqual(signup.status_code, 200, signup.text)

        admin_token, _admin_payload = self._login("admin@test.local", "AdminPass1234")
        pending = self.client.get("/admin/users/pending", headers=self._auth_headers(admin_token))
        self.assertEqual(pending.status_code, 200, pending.text)
        target = next((u for u in pending.json()["items"] if u["email"] == email), None)
        self.assertIsNotNone(target, pending.text)

        approve = self.client.post(
            f"/admin/users/{target['id']}/approve",
            headers=self._auth_headers(admin_token),
        )
        self.assertEqual(approve.status_code, 200, approve.text)
        return email, password

    def test_protected_exports_require_authentication(self):
        self.client.cookies.clear()
        compare = self.client.post(
            "/compare/export-pdf",
            json={"ideal_spec": {"product_name": "office downlight"}, "codes": ["Project requirement", "156480-00"]},
        )
        self.assertEqual(compare.status_code, 401, compare.text)

        quote_pdf = self.client.post(
            "/quote/export-pdf",
            json={"company": "Test Co", "project": "Project A", "items": [{"product_code": "156480-00"}]},
        )
        self.assertEqual(quote_pdf.status_code, 401, quote_pdf.text)

        datasheets_zip = self.client.post(
            "/quote/datasheets-zip",
            json={"items": [{"product_code": "156480-00", "manufacturer": "Disano"}]},
        )
        self.assertEqual(datasheets_zip.status_code, 401, datasheets_zip.text)

    def test_user_quote_history_is_sorted_by_project_name(self):
        email, password = self._create_and_approve_user()
        user_token, login_payload = self._login(email, password)
        self.assertEqual(login_payload["user"]["company_name"], "Journey Co")
        headers = self._auth_headers(user_token)

        base_item = {
            "product_code": "156480-00",
            "product_name": "Health Dark GOLD UGR<19",
            "manufacturer": "Disano",
            "qty": 2,
            "notes": "Check mounting",
            "project_reference": "L1",
            "source": "finder-exact",
            "sort_order": 0,
            "compare_sheet": {"ideal_spec": {"product_name": "office downlight", "ugr": "<=19"}, "source": "finder-exact"},
        }
        for project_name in ("Zeta Project", "Alpha Project"):
            response = self.client.post(
                "/auth/quotes",
                headers=headers,
                json={
                    "company": "Journey Co",
                    "project": project_name,
                    "project_status": "design_phase",
                    "contractor_name": "Unavailable",
                    "consultant_name": "Unavailable",
                    "project_notes": f"Notes for {project_name}",
                    "items": [base_item],
                },
            )
            self.assertEqual(response.status_code, 200, response.text)

        quotes = self.client.get("/auth/quotes", headers=headers)
        self.assertEqual(quotes.status_code, 200, quotes.text)
        projects = [item["project"] for item in quotes.json()["items"]]
        self.assertEqual(projects, ["Alpha Project", "Zeta Project"])
        self.assertEqual(quotes.json()["items"][0]["project_status"], "design_phase")
        self.assertTrue(str(quotes.json()["items"][0]["project_notes"]).startswith("Notes for "))

    def test_authenticated_exports_work_for_approved_user(self):
        email, password = self._create_and_approve_user()
        user_token, _payload = self._login(email, password)
        headers = self._auth_headers(user_token)

        compare = self.client.post(
            "/compare/export-pdf",
            headers=headers,
            json={"ideal_spec": {"product_name": "office downlight", "ugr": "<=19"}, "codes": ["Project requirement", "156480-00"]},
        )
        self.assertEqual(compare.status_code, 200, compare.text)
        self.assertEqual(compare.headers.get("content-type"), "application/pdf")

        items = [{
            "product_code": "156480-00",
            "product_name": "Health Dark GOLD UGR<19",
            "manufacturer": "Disano",
            "qty": 2,
            "notes": "Check mounting",
            "project_reference": "L1",
            "source": "finder-exact",
        }]
        quote_pdf = self.client.post(
            "/quote/export-pdf",
            headers=headers,
            json={
                "company": "Journey Co",
                "project": "Export Project",
                "project_status": "tender",
                "contractor_name": "Unavailable",
                "consultant_name": "Unavailable",
                "project_notes": "Client review scheduled next week.",
                "items": items,
            },
        )
        self.assertEqual(quote_pdf.status_code, 200, quote_pdf.text)
        self.assertEqual(quote_pdf.headers.get("content-type"), "application/pdf")

        datasheets_zip = self.client.post(
            "/quote/datasheets-zip",
            headers=headers,
            json={"items": [{"product_code": "156480-00", "manufacturer": "Disano"}]},
        )
        self.assertEqual(datasheets_zip.status_code, 200, datasheets_zip.text)
        self.assertEqual(datasheets_zip.headers.get("content-type"), "application/zip")


if __name__ == "__main__":
    unittest.main()
