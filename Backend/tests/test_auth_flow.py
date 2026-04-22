import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_env = {k: os.environ.get(k) for k in [
            "AUTH_DB_PATH",
            "AUTH_DATABASE_URL",
            "AUTH_JWT_SECRET",
            "ADMIN_BOOTSTRAP_EMAIL",
            "ADMIN_BOOTSTRAP_PASSWORD",
            "ADMIN_BOOTSTRAP_NAME",
            "PF_SKIP_RUNTIME_INIT",
            "SMTP_FROM_EMAIL",
        ]}
        cls._tmpdir = tempfile.TemporaryDirectory()
        os.environ["AUTH_DB_PATH"] = os.path.join(cls._tmpdir.name, "auth.db")
        os.environ["AUTH_DATABASE_URL"] = ""
        os.environ["AUTH_JWT_SECRET"] = "test-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
        os.environ["ADMIN_BOOTSTRAP_EMAIL"] = "admin@test.local"
        os.environ["ADMIN_BOOTSTRAP_PASSWORD"] = "AdminPass1234"
        os.environ["ADMIN_BOOTSTRAP_NAME"] = "Test Admin"
        os.environ["PF_SKIP_RUNTIME_INIT"] = "1"
        os.environ["SMTP_FROM_EMAIL"] = "info@sofoenix.com"

        try:
            from fastapi.testclient import TestClient
            main = importlib.import_module("app.main")
            main = importlib.reload(main)
        except Exception as e:  # pragma: no cover - env-dependent
            raise unittest.SkipTest(f"Skipping auth flow test (import/setup failed): {e}")

        cls.main = main
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

    def test_signup_approve_login_flow(self):
        signup_payload = {
            "email": "new.user@test.local",
            "password": "StrongPass123",
            "full_name": "New User",
            "company_name": "Acme Lighting",
            "country": "Italy",
        }
        signup = self.client.post("/auth/signup", json=signup_payload)
        self.assertEqual(signup.status_code, 200, signup.text)
        self.assertEqual(signup.json()["user"]["status"], "pending")

        denied_login = self.client.post(
            "/auth/login",
            json={"email": signup_payload["email"], "password": signup_payload["password"]},
        )
        self.assertEqual(denied_login.status_code, 403, denied_login.text)

        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "AdminPass1234"},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        pending = self.client.get("/admin/users/pending", headers=admin_headers)
        self.assertEqual(pending.status_code, 200, pending.text)
        pending_items = pending.json()["items"]
        target = next((item for item in pending_items if item["email"] == signup_payload["email"]), None)
        self.assertIsNotNone(target, pending.text)
        user_id = target["id"]

        approved = self.client.post(f"/admin/users/{user_id}/approve", headers=admin_headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["user"]["status"], "approved")

        user_login = self.client.post(
            "/auth/login",
            json={"email": signup_payload["email"], "password": signup_payload["password"]},
        )
        self.assertEqual(user_login.status_code, 200, user_login.text)
        user_token = user_login.json()["access_token"]

        me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["email"], signup_payload["email"])
        self.assertEqual(me.json()["role"], "user")
        self.assertEqual(me.json()["status"], "approved")
        self.assertEqual(me.json()["company_name"], "Acme Lighting")

        quote_payload = {
            "company": "ACME",
            "project": "Airport relamping",
            "project_status": "design_phase",
            "contractor_name": "Unavailable",
            "consultant_name": "Unavailable",
            "project_notes": "Client wants first draft before Friday.",
            "items": [
                {
                    "product_code": "620LED",
                    "product_name": "Sample",
                    "manufacturer": "Disano",
                    "qty": 2,
                    "notes": "Priority area",
                    "project_reference": "APR-01",
                    "source": "finder-exact",
                    "sort_order": 0,
                    "compare_sheet": {
                        "ideal_spec": {"product_name": "office downlight", "ugr": "<=19"},
                        "source": "finder-exact",
                    },
                }
            ],
        }
        created_quote = self.client.post(
            "/auth/quotes",
            json=quote_payload,
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(created_quote.status_code, 200, created_quote.text)
        quote_id = created_quote.json()["quote"]["id"]
        self.assertEqual(created_quote.json()["quote"]["project"], "Airport relamping")
        self.assertEqual(created_quote.json()["quote"]["project_status"], "design_phase")
        self.assertEqual(created_quote.json()["quote"]["contractor_name"], "Unavailable")
        self.assertEqual(created_quote.json()["quote"]["consultant_name"], "Unavailable")
        self.assertEqual(created_quote.json()["quote"]["project_notes"], "Client wants first draft before Friday.")
        self.assertEqual(created_quote.json()["quote"]["item_count"], 1)

        quote_list = self.client.get("/auth/quotes", headers={"Authorization": f"Bearer {user_token}"})
        self.assertEqual(quote_list.status_code, 200, quote_list.text)
        self.assertEqual(quote_list.json()["count"], 1)
        self.assertEqual(quote_list.json()["items"][0]["project"], "Airport relamping")
        self.assertEqual(quote_list.json()["items"][0]["project_status"], "design_phase")

        loaded_quote = self.client.get(
            f"/auth/quotes/{quote_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(loaded_quote.status_code, 200, loaded_quote.text)
        self.assertEqual(loaded_quote.json()["items"][0]["project_reference"], "APR-01")
        self.assertEqual(loaded_quote.json()["project_notes"], "Client wants first draft before Friday.")
        self.assertEqual(loaded_quote.json()["contractor_name"], "Unavailable")
        self.assertEqual(loaded_quote.json()["consultant_name"], "Unavailable")

        updated_quote = self.client.put(
            f"/auth/quotes/{quote_id}",
            json={**quote_payload, "project": "Airport relamping revised", "project_status": "job_in_hand"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(updated_quote.status_code, 200, updated_quote.text)
        self.assertEqual(updated_quote.json()["quote"]["project"], "Airport relamping revised")
        self.assertEqual(updated_quote.json()["quote"]["project_status"], "job_in_hand")

        deleted_quote = self.client.delete(
            f"/auth/quotes/{quote_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(deleted_quote.status_code, 200, deleted_quote.text)
        self.assertEqual(deleted_quote.json()["deleted"], quote_id)

        quote_list_after_delete = self.client.get("/auth/quotes", headers={"Authorization": f"Bearer {user_token}"})
        self.assertEqual(quote_list_after_delete.status_code, 200, quote_list_after_delete.text)
        self.assertEqual(quote_list_after_delete.json()["count"], 0)

        unauth_suggest = self.client.get("/codes/suggest", params={"q": "620"})
        self.assertEqual(unauth_suggest.status_code, 200, unauth_suggest.text)

        auth_suggest = self.client.get(
            "/codes/suggest",
            params={"q": "620"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(auth_suggest.status_code, 200, auth_suggest.text)

    def test_cookie_session_refresh_and_logout_flow(self):
        signup_payload = {
            "email": "cookie.user@test.local",
            "password": "StrongPass123",
            "full_name": "Cookie User",
            "company_name": "Cookie Lighting",
            "country": "Italy",
        }
        signup = self.client.post("/auth/signup", json=signup_payload)
        self.assertEqual(signup.status_code, 200, signup.text)

        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "AdminPass1234"},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        admin_token = admin_login.json()["access_token"]
        pending = self.client.get("/admin/users/pending", headers={"Authorization": f"Bearer {admin_token}"})
        user_id = next(item["id"] for item in pending.json()["items"] if item["email"] == signup_payload["email"])
        approved = self.client.post(f"/admin/users/{user_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(approved.status_code, 200, approved.text)

        login = self.client.post(
            "/auth/login",
            json={"email": signup_payload["email"], "password": signup_payload["password"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertIn("pf_access_token", self.client.cookies)
        self.assertIn("pf_refresh_token", self.client.cookies)

        me = self.client.get("/auth/me")
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["email"], signup_payload["email"])

        self.client.cookies.delete("pf_access_token")
        refreshed = self.client.post("/auth/refresh")
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertIn("pf_access_token", self.client.cookies)

        me_after_refresh = self.client.get("/auth/me")
        self.assertEqual(me_after_refresh.status_code, 200, me_after_refresh.text)
        self.assertEqual(me_after_refresh.json()["company_name"], "Cookie Lighting")

        logout = self.client.post("/auth/logout")
        self.assertEqual(logout.status_code, 200, logout.text)
        after_logout = self.client.get("/auth/me")
        self.assertEqual(after_logout.status_code, 401, after_logout.text)

    def test_admin_settings_are_masked_and_updatable(self):
        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "AdminPass1234"},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        settings_before = self.client.get("/admin/settings", headers=admin_headers)
        self.assertEqual(settings_before.status_code, 200, settings_before.text)
        self.assertGreaterEqual(settings_before.json()["count"], 1)

        update_secret = self.client.put(
            "/admin/settings/openai_api_key",
            json={"value": "sk-test-secret-value"},
            headers=admin_headers,
        )
        self.assertEqual(update_secret.status_code, 200, update_secret.text)
        self.assertTrue(update_secret.json()["setting"]["configured"])
        self.assertEqual(update_secret.json()["setting"]["value"], "")
        self.assertNotEqual(update_secret.json()["setting"]["masked_value"], "")

        update_non_secret = self.client.put(
            "/admin/settings/auth_token_expire_minutes",
            json={"value": "90"},
            headers=admin_headers,
        )
        self.assertEqual(update_non_secret.status_code, 200, update_non_secret.text)
        self.assertEqual(update_non_secret.json()["setting"]["value"], "90")

    def test_manager_cannot_access_analytics_summary(self):
        signup_payload = {
            "email": "manager.user@test.local",
            "password": "StrongPass123",
            "full_name": "Manager User",
            "company_name": "Manager Lighting",
            "country": "Italy",
        }
        signup = self.client.post("/auth/signup", json=signup_payload)
        self.assertEqual(signup.status_code, 200, signup.text)

        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "AdminPass1234"},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        pending = self.client.get("/admin/users/pending", headers=admin_headers)
        self.assertEqual(pending.status_code, 200, pending.text)
        user_id = next(item["id"] for item in pending.json()["items"] if item["email"] == signup_payload["email"])

        approved = self.client.post(
            f"/admin/users/{user_id}/approve",
            json={"role": "manager", "assigned_countries": ["Italy"]},
            headers=admin_headers,
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["user"]["role"], "manager")

        manager_login = self.client.post(
            "/auth/login",
            json={"email": signup_payload["email"], "password": signup_payload["password"]},
        )
        self.assertEqual(manager_login.status_code, 200, manager_login.text)
        manager_token = manager_login.json()["access_token"]
        manager_headers = {"Authorization": f"Bearer {manager_token}"}

        users_visible = self.client.get("/admin/users", headers=manager_headers)
        self.assertEqual(users_visible.status_code, 200, users_visible.text)

        analytics = self.client.get("/admin/analytics/summary", headers=manager_headers)
        self.assertEqual(analytics.status_code, 403, analytics.text)

        release_diff = self.client.get("/admin/catalog-release-diff", headers=manager_headers)
        self.assertEqual(release_diff.status_code, 403, release_diff.text)

    def test_signup_and_approval_emails_go_to_expected_recipients(self):
        sent_messages = []

        def fake_send_email(self, *, to_email: str, subject: str, body: str):
            sent_messages.append(
                {
                    "to_email": str(to_email or ""),
                    "subject": str(subject or ""),
                    "body": str(body or ""),
                }
            )

        signup_payload = {
            "email": "mail.user@test.local",
            "password": "StrongPass123",
            "full_name": "Mail User",
            "company_name": "Mail Lighting",
            "country": "Italy",
        }

        with patch("app.auth.AuthService._send_email", new=fake_send_email):
            signup = self.client.post("/auth/signup", json=signup_payload)
            self.assertEqual(signup.status_code, 200, signup.text)

            self.assertEqual(len(sent_messages), 2)
            self.assertEqual(sent_messages[0]["to_email"], "info@sofoenix.com")
            self.assertIn("New Laiting access request", sent_messages[0]["subject"])
            self.assertIn("mail.user@test.local", sent_messages[0]["body"])
            self.assertEqual(sent_messages[1]["to_email"], "mail.user@test.local")
            self.assertIn("We received your Laiting access request", sent_messages[1]["subject"])

            admin_login = self.client.post(
                "/auth/login",
                json={"email": "admin@test.local", "password": "AdminPass1234"},
            )
            self.assertEqual(admin_login.status_code, 200, admin_login.text)
            admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
            pending = self.client.get("/admin/users/pending", headers=admin_headers)
            self.assertEqual(pending.status_code, 200, pending.text)
            user_id = next(item["id"] for item in pending.json()["items"] if item["email"] == signup_payload["email"])

            approved = self.client.post(f"/admin/users/{user_id}/approve", headers=admin_headers)
            self.assertEqual(approved.status_code, 200, approved.text)

        self.assertEqual(len(sent_messages), 3)
        self.assertEqual(sent_messages[2]["to_email"], "mail.user@test.local")
        self.assertIn("Your Laiting access has been approved", sent_messages[2]["subject"])
        self.assertNotIn("admin@test.local", [sent_messages[2]["to_email"]])

        settings_after = self.client.get("/admin/settings", headers=admin_headers)
        self.assertEqual(settings_after.status_code, 200, settings_after.text)
        by_key = {item["key"]: item for item in settings_after.json()["items"]}
        self.assertEqual(by_key["auth_token_expire_minutes"]["value"], "90")
        self.assertTrue(by_key["openai_api_key"]["configured"])
        self.assertEqual(by_key["openai_api_key"]["value"], "")

    def test_director_can_access_analytics_and_manage_roles_but_not_settings(self):
        director_signup = {
            "email": "director.user@test.local",
            "password": "StrongPass123",
            "full_name": "Director User",
            "company_name": "Director Lighting",
            "country": "Italy",
        }
        promoted_signup = {
            "email": "promoted.user@test.local",
            "password": "StrongPass123",
            "full_name": "Promoted User",
            "company_name": "Promoted Lighting",
            "country": "Spain",
        }
        admin_target_signup = {
            "email": "admin.target@test.local",
            "password": "StrongPass123",
            "full_name": "Admin Target",
            "company_name": "Admin Lighting",
            "country": "France",
        }
        pending_signup = {
            "email": "pending.user@test.local",
            "password": "StrongPass123",
            "full_name": "Pending User",
            "company_name": "Pending Lighting",
            "country": "Germany",
        }
        for payload in [director_signup, promoted_signup, admin_target_signup, pending_signup]:
            signup = self.client.post("/auth/signup", json=payload)
            self.assertEqual(signup.status_code, 200, signup.text)

        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "AdminPass1234"},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        pending = self.client.get("/admin/users/pending", headers=admin_headers)
        self.assertEqual(pending.status_code, 200, pending.text)
        pending_by_email = {item["email"]: item for item in pending.json()["items"]}

        director_approved = self.client.post(
            f"/admin/users/{pending_by_email[director_signup['email']]['id']}/approve",
            json={"role": "director"},
            headers=admin_headers,
        )
        self.assertEqual(director_approved.status_code, 200, director_approved.text)
        self.assertEqual(director_approved.json()["user"]["role"], "director")

        promoted_approved = self.client.post(
            f"/admin/users/{pending_by_email[promoted_signup['email']]['id']}/approve",
            headers=admin_headers,
        )
        self.assertEqual(promoted_approved.status_code, 200, promoted_approved.text)

        admin_target_approved = self.client.post(
            f"/admin/users/{pending_by_email[admin_target_signup['email']]['id']}/approve",
            json={"role": "admin"},
            headers=admin_headers,
        )
        self.assertEqual(admin_target_approved.status_code, 200, admin_target_approved.text)

        director_login = self.client.post(
            "/auth/login",
            json={"email": director_signup["email"], "password": director_signup["password"]},
        )
        self.assertEqual(director_login.status_code, 200, director_login.text)
        director_token = director_login.json()["access_token"]
        director_headers = {"Authorization": f"Bearer {director_token}"}

        analytics = self.client.get("/admin/analytics/summary", headers=director_headers)
        self.assertEqual(analytics.status_code, 200, analytics.text)

        original_product_db = self.main.PRODUCT_DB
        try:
            class _ReleaseDiffStub:
                def get_latest_release_diff(self):
                    return {"has_release": True, "summary": {"release_id": 1}, "items": []}

            self.main.PRODUCT_DB = _ReleaseDiffStub()
            release_diff = self.client.get("/admin/catalog-release-diff", headers=director_headers)
            self.assertEqual(release_diff.status_code, 200, release_diff.text)
        finally:
            self.main.PRODUCT_DB = original_product_db

        pending_for_director = self.client.get("/admin/users/pending", headers=director_headers)
        self.assertEqual(pending_for_director.status_code, 200, pending_for_director.text)
        pending_items = pending_for_director.json()["items"]
        pending_map = {item["email"]: item for item in pending_items}
        self.assertIn(pending_signup["email"], pending_map)

        approve_manager = self.client.post(
            f"/admin/users/{pending_map[pending_signup['email']]['id']}/approve",
            json={"role": "manager", "assigned_countries": ["Germany"]},
            headers=director_headers,
        )
        self.assertEqual(approve_manager.status_code, 200, approve_manager.text)
        self.assertEqual(approve_manager.json()["user"]["role"], "manager")

        promoted_user_id = promoted_approved.json()["user"]["id"]
        promote_to_director = self.client.put(
            f"/admin/users/{promoted_user_id}",
            json={
                "full_name": promoted_signup["full_name"],
                "company_name": promoted_signup["company_name"],
                "country": promoted_signup["country"],
                "role": "director",
                "assigned_countries": [],
            },
            headers=director_headers,
        )
        self.assertEqual(promote_to_director.status_code, 200, promote_to_director.text)
        self.assertEqual(promote_to_director.json()["user"]["role"], "director")

        admin_target_user_id = admin_target_approved.json()["user"]["id"]
        forbidden_admin_promotion = self.client.put(
            f"/admin/users/{admin_target_user_id}",
            json={
                "full_name": admin_target_signup["full_name"],
                "company_name": admin_target_signup["company_name"],
                "country": admin_target_signup["country"],
                "role": "admin",
                "assigned_countries": [],
            },
            headers=director_headers,
        )
        self.assertEqual(forbidden_admin_promotion.status_code, 403, forbidden_admin_promotion.text)

        director_settings = self.client.get("/admin/settings", headers=director_headers)
        self.assertEqual(director_settings.status_code, 403, director_settings.text)

    def test_manager_and_director_visible_quotes_table_scope(self):
        records = [
            {
                "email": "quotes.manager@test.local",
                "password": "StrongPass123",
                "full_name": "Quotes Manager",
                "company_name": "Manager Lighting",
                "country": "Italy",
                "role": "manager",
                "assigned_countries": ["Italy"],
            },
            {
                "email": "quotes.director@test.local",
                "password": "StrongPass123",
                "full_name": "Quotes Director",
                "company_name": "Director Lighting",
                "country": "Italy",
                "role": "director",
                "assigned_countries": [],
            },
            {
                "email": "quotes.italy@test.local",
                "password": "StrongPass123",
                "full_name": "Italy Seller",
                "company_name": "Italy Customer Spa",
                "country": "Italy",
                "role": "user",
                "assigned_countries": [],
            },
            {
                "email": "quotes.spain@test.local",
                "password": "StrongPass123",
                "full_name": "Spain Seller",
                "company_name": "Spain Customer SL",
                "country": "Spain",
                "role": "user",
                "assigned_countries": [],
            },
        ]
        for payload in records:
            signup = self.client.post(
                "/auth/signup",
                json={
                    "email": payload["email"],
                    "password": payload["password"],
                    "full_name": payload["full_name"],
                    "company_name": payload["company_name"],
                    "country": payload["country"],
                },
            )
            self.assertEqual(signup.status_code, 200, signup.text)

        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "AdminPass1234"},
        )
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        pending = self.client.get("/admin/users/pending", headers=admin_headers)
        self.assertEqual(pending.status_code, 200, pending.text)
        by_email = {item["email"]: item for item in pending.json()["items"]}

        for payload in records:
            approved = self.client.post(
                f"/admin/users/{by_email[payload['email']]['id']}/approve",
                json={"role": payload["role"], "assigned_countries": payload["assigned_countries"]},
                headers=admin_headers,
            )
            self.assertEqual(approved.status_code, 200, approved.text)

        user_quotes = [
            ("quotes.italy@test.local", "StrongPass123", "Milan Hospital", "Italy Customer Spa", "BuildItalia", "Studio Uno"),
            ("quotes.spain@test.local", "StrongPass123", "Madrid Airport", "Spain Customer SL", "Construcciones Iberia", "Consultores Luz"),
        ]
        for email, password, project, company, contractor, consultant in user_quotes:
            login = self.client.post("/auth/login", json={"email": email, "password": password})
            self.assertEqual(login.status_code, 200, login.text)
            user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            saved = self.client.post(
                "/auth/quotes",
                json={
                    "company": company,
                    "project": project,
                    "project_status": "tender",
                    "contractor_name": contractor,
                    "consultant_name": consultant,
                    "project_notes": "",
                    "items": [
                        {
                            "product_code": "620LED",
                            "product_name": "Sample",
                            "manufacturer": "Disano",
                            "qty": 1,
                            "notes": "",
                            "project_reference": "",
                            "source": "finder-exact",
                            "sort_order": 0,
                            "compare_sheet": {},
                        }
                    ],
                },
                headers=user_headers,
            )
            self.assertEqual(saved.status_code, 200, saved.text)

        manager_login = self.client.post(
            "/auth/login",
            json={"email": "quotes.manager@test.local", "password": "StrongPass123"},
        )
        self.assertEqual(manager_login.status_code, 200, manager_login.text)
        manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}
        manager_quotes = self.client.get("/admin/quotes", headers=manager_headers)
        self.assertEqual(manager_quotes.status_code, 200, manager_quotes.text)
        self.assertEqual(manager_quotes.json()["count"], 1)
        self.assertEqual(manager_quotes.json()["items"][0]["project"], "Milan Hospital")
        self.assertEqual(manager_quotes.json()["items"][0]["country"], "Italy")
        self.assertEqual(manager_quotes.json()["items"][0]["customer_name"], "Italy Customer Spa")
        self.assertEqual(manager_quotes.json()["items"][0]["contractor_name"], "BuildItalia")
        self.assertEqual(manager_quotes.json()["items"][0]["consultant_name"], "Studio Uno")

        director_login = self.client.post(
            "/auth/login",
            json={"email": "quotes.director@test.local", "password": "StrongPass123"},
        )
        self.assertEqual(director_login.status_code, 200, director_login.text)
        director_headers = {"Authorization": f"Bearer {director_login.json()['access_token']}"}
        director_quotes = self.client.get("/admin/quotes", headers=director_headers)
        self.assertEqual(director_quotes.status_code, 200, director_quotes.text)
        self.assertEqual(director_quotes.json()["count"], 2)
        project_names = {item["project"] for item in director_quotes.json()["items"]}
        self.assertEqual(project_names, {"Milan Hospital", "Madrid Airport"})

    def test_password_reset_request_and_confirm_flow(self):
        signup_payload = {
            "email": "reset.user@test.local",
            "password": "StrongPass123",
            "full_name": "Reset User",
            "company_name": "Reset Lighting",
            "country": "Italy",
        }
        signup = self.client.post("/auth/signup", json=signup_payload)
        self.assertEqual(signup.status_code, 200, signup.text)

        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@test.local", "password": "AdminPass1234"},
        )
        admin_token = admin_login.json()["access_token"]
        pending = self.client.get("/admin/users/pending", headers={"Authorization": f"Bearer {admin_token}"})
        user_id = next(item["id"] for item in pending.json()["items"] if item["email"] == signup_payload["email"])
        approved = self.client.post(f"/admin/users/{user_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(approved.status_code, 200, approved.text)

        captured = {}
        original_sender = self.main.auth_service._send_password_reset_email
        try:
          def capture_reset_email(*, to_email, reset_url):
              captured["email"] = to_email
              captured["reset_url"] = reset_url
          self.main.auth_service._send_password_reset_email = capture_reset_email

          requested = self.client.post("/auth/password-reset/request", json={"email": signup_payload["email"]})
          self.assertEqual(requested.status_code, 200, requested.text)
          self.assertEqual(captured["email"], signup_payload["email"])
          self.assertIn("token=", captured["reset_url"])

          token = captured["reset_url"].split("token=", 1)[1]
          confirmed = self.client.post(
              "/auth/password-reset/confirm",
              json={"token": token, "password": "EvenBetter456"},
          )
          self.assertEqual(confirmed.status_code, 200, confirmed.text)
        finally:
          self.main.auth_service._send_password_reset_email = original_sender

        old_login = self.client.post(
            "/auth/login",
            json={"email": signup_payload["email"], "password": signup_payload["password"]},
        )
        self.assertEqual(old_login.status_code, 401, old_login.text)

        new_login = self.client.post(
            "/auth/login",
            json={"email": signup_payload["email"], "password": "EvenBetter456"},
        )
        self.assertEqual(new_login.status_code, 200, new_login.text)


if __name__ == "__main__":
    unittest.main()
