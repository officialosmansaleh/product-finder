import os
import unittest


def main() -> int:
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    test_dir = os.path.dirname(__file__)
    suite.addTests(loader.discover(test_dir, pattern="test_local_parser_multilang_*.py"))
    suite.addTests(loader.discover(test_dir, pattern="test_debug_parse_api_regression.py"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
