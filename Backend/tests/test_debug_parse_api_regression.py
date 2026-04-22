import os
import sys
import unittest


_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class DebugParseApiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ENABLE_DEBUG_ENDPOINTS"] = "true"
        try:
            import importlib
            from fastapi.testclient import TestClient
            import app.main as main
        except Exception as e:  # pragma: no cover - env-dependent
            raise unittest.SkipTest(f"Skipping API regression test (import/setup failed): {e}")
        main = importlib.reload(main)
        cls.client_cm = TestClient(main.app)
        cls.client = cls.client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)

    def test_debug_parse_returns_local_and_sql(self):
        q = "proyector exterior al menos ip65 diametro 180"
        r = self.client.get("/debug/parse", params={"q": q})
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertIn("local", data)
        self.assertIn("sql", data)
        self.assertEqual(data.get("q"), q)
        local = data["local"]
        self.assertEqual(local.get("product_family"), "floodlight")
        self.assertEqual(local.get("ip_rating"), ">=IP65")
        self.assertEqual(local.get("diameter"), ">=180")
        # SQL mapping should preserve normalized values for current fields.
        self.assertEqual(data["sql"].get("ip_rating"), ">=IP65")


if __name__ == "__main__":
    unittest.main()
