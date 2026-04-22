import os
import sys
import tempfile
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class ConsentAnalyticsTests(unittest.TestCase):
    def test_consent_cookie_roundtrip_and_summary(self):
        from app.auth import AuthService, UserPublic, SignupRequest

        with tempfile.TemporaryDirectory() as tmp:
            service = AuthService(db_path=os.path.join(tmp, "auth.db"))
            service.init_db()
            tracked_user = service.create_signup(
                SignupRequest(
                    email="buyer@example.com",
                    password="BuyerPass123",
                    full_name="Buyer User",
                    company_name="Acme Lighting",
                    country="Italy",
                )
            )

            cookie = service.encode_consent_cookie(
                analytics_enabled=True,
                consent_version="2026-03-31",
                updated_at="2026-03-31T10:00:00+00:00",
            )
            decoded = service.decode_consent_cookie(cookie)
            self.assertEqual(decoded["analytics"], True)
            self.assertEqual(decoded["version"], "2026-03-31")

            service.upsert_consent_preference(
                analytics_enabled=True,
                consent_version="2026-03-31",
                source="test",
                session_id="sid-1",
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="search",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="finder",
                path="/search",
                query_text="street lighting",
                filters={"product_family": "Street lighting"},
                metadata={"exact_count": 12},
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="search",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="finder",
                path="/search",
                query_text="road",
                filters={"product_family": "Street lighting"},
                metadata={"exact_count": 0, "similar_count": 4, "requested_family": "Street lighting"},
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="search",
                session_id="sid-2",
                page="finder",
                path="/search",
                query_text="warehouse emergency",
                filters={},
                metadata={"exact_count": 0, "similar_count": 0},
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="product_open_datasheet",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="finder",
                path="/search",
                product_code="ST-100",
                query_text="street lighting",
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="compare_add_from_search",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="finder",
                path="/search",
                product_code="ST-100",
                query_text="street lighting",
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="quote_add_from_search",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="finder",
                path="/search",
                product_code="ST-100",
                query_text="street lighting",
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="quote_save",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="quote",
                path="/auth/quotes",
                query_text="Project Alpha",
                metadata={"item_count": 3, "quote_id": 10},
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="quote_export_pdf",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="quote",
                path="/quote/export-pdf",
                query_text="Project Alpha",
                metadata={"item_count": 3},
                ip_address="127.0.0.1",
                user_agent="pytest",
            )
            service.record_activity_event(
                event_type="quote_datasheets_zip",
                session_id="sid-1",
                user_id=tracked_user.id,
                page="quote",
                path="/quote/datasheets-zip",
                query_text="Project Alpha",
                metadata={"item_count": 3},
                ip_address="127.0.0.1",
                user_agent="pytest",
            )

            viewer = UserPublic(
                id=1,
                email="admin@example.com",
                full_name="Admin User",
                company_name="",
                country="Italy",
                assigned_countries=[],
                role="admin",
                status="approved",
                created_at="2026-03-31T10:00:00+00:00",
            )
            summary = service.get_analytics_summary(viewer, days=30, top_n=5)
            self.assertEqual(summary["totals"]["events"], 9)
            self.assertEqual(summary["totals"]["searches"], 3)
            self.assertEqual(summary["totals"]["sessions"], 2)
            self.assertEqual(summary["totals"]["zero_result_searches"], 1)
            self.assertEqual(summary["totals"]["searches_without_exact"], 2)
            self.assertEqual(summary["totals"]["quote_saves"], 1)
            self.assertEqual(summary["totals"]["quote_exports"], 1)
            self.assertIn(
                "street lighting",
                {row["query_text"] for row in summary["top_searches"]},
            )
            self.assertEqual(summary["top_no_result_searches"][0]["query_text"], "warehouse emergency")
            self.assertIn(
                "road",
                {row["query_text"] for row in summary["top_searches_without_exact"]},
            )
            self.assertEqual(summary["top_requested_families"][0]["family"], "Street lighting")
            self.assertEqual(summary["top_gap_families"][0]["family"], "Street lighting")
            self.assertEqual(summary["top_gap_families"][0]["count"], 1)
            gap_map = {
                (row["family"], row["example_query"]): row
                for row in summary["top_catalog_gaps"]
            }
            self.assertEqual(gap_map[("Street lighting", "road")]["gap_type"], "closest_only")
            self.assertEqual(gap_map[("Unclassified search", "warehouse emergency")]["gap_type"], "no_result")
            self.assertEqual(summary["quote_funnel"]["saved"], 1)
            self.assertEqual(summary["quote_funnel"]["exported_pdf"], 1)
            self.assertEqual(summary["quote_funnel"]["datasheets_zip"], 1)
            journey = {row["key"]: row for row in summary["journey_funnel"]}
            self.assertEqual(journey["search_started"]["sessions"], 2)
            self.assertEqual(journey["search_with_results"]["sessions"], 1)
            self.assertEqual(journey["product_interaction"]["sessions"], 1)
            self.assertEqual(journey["compare_used"]["sessions"], 1)
            self.assertEqual(journey["quote_built"]["sessions"], 1)
            self.assertEqual(journey["quote_exported"]["sessions"], 1)
            self.assertEqual(journey["search_with_results"]["conversion_from_previous"], 50.0)
            self.assertEqual(summary["top_viewed_products"][0]["product_code"], "ST-100")
            self.assertEqual(summary["top_compared_products"][0]["product_code"], "ST-100")
            self.assertEqual(summary["top_quoted_products"][0]["product_code"], "ST-100")
            self.assertEqual(summary["top_product_intent"][0]["product_code"], "ST-100")
            self.assertEqual(summary["top_product_intent"][0]["views"], 1)
            self.assertEqual(summary["top_product_intent"][0]["compares"], 1)
            self.assertEqual(summary["top_product_intent"][0]["quotes"], 1)
            self.assertEqual(summary["top_product_intent"][0]["intent_score"], 6)
            self.assertEqual(summary["top_companies"][0]["company_name"], "Acme Lighting")
            self.assertEqual(summary["top_companies"][0]["searches"], 2)
            self.assertEqual(summary["top_companies"][0]["quote_saves"], 1)
            self.assertEqual(summary["top_companies"][0]["quote_exports"], 1)
            self.assertEqual(summary["country_insights"][0]["country"], "Italy")
            self.assertEqual(summary["country_insights"][0]["searches"], 2)
            self.assertEqual(summary["country_insights"][0]["quote_saves"], 1)
            self.assertEqual(summary["country_insights"][0]["quote_exports"], 1)


if __name__ == "__main__":
    unittest.main()
