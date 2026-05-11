import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SqlSafetyTest(unittest.TestCase):
    def test_unterminated_leading_block_comment_fails_closed(self) -> None:
        from sql_safety import referenced_sql_tables, validate_sql_allowed_tables

        with self.assertRaises(ValueError):
            referenced_sql_tables("/* unfinished comment SELECT * FROM users")

        allowed, error = validate_sql_allowed_tables("/* unfinished comment SELECT * FROM users")

        self.assertFalse(allowed)
        self.assertEqual(error, "Unterminated SQL block comment")


if __name__ == "__main__":
    unittest.main()
