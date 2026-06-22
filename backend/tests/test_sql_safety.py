import unittest

from backend.app.sql_safety import referenced_sql_tables, validate_sql_allowed_tables


class SqlSafetyTest(unittest.TestCase):
    def test_unterminated_leading_block_comment_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            referenced_sql_tables("/* unfinished comment SELECT * FROM users")

        allowed, error = validate_sql_allowed_tables("/* unfinished comment SELECT * FROM users")

        self.assertFalse(allowed)
        self.assertEqual(error, "Unterminated SQL block comment")

    def test_leading_line_and_block_comments_are_ignored(self) -> None:
        sql = "-- comment\n/* another comment */ SELECT * FROM users"

        self.assertEqual(referenced_sql_tables(sql), {"users"})
        self.assertEqual(validate_sql_allowed_tables(sql), (True, ""))

    def test_multiple_leading_comments_are_ignored(self) -> None:
        sql = "-- one\n-- two\n/* three */ SELECT * FROM user_types"

        self.assertEqual(referenced_sql_tables(sql), {"user_types"})
        self.assertEqual(validate_sql_allowed_tables(sql), (True, ""))

    def test_leading_cte_is_rejected_after_comments(self) -> None:
        with self.assertRaises(ValueError):
            referenced_sql_tables("-- comment\nWITH scoped AS (SELECT * FROM users) SELECT * FROM scoped")

    def test_nested_subquery_is_rejected(self) -> None:
        allowed, error = validate_sql_allowed_tables("SELECT * FROM (SELECT * FROM users) scoped")

        self.assertFalse(allowed)
        self.assertEqual(error, "Nested subqueries are not supported in read-only admin SQL")

    def test_disallowed_tables_are_reported(self) -> None:
        allowed, error = validate_sql_allowed_tables("SELECT * FROM user_memories")

        self.assertFalse(allowed)
        self.assertEqual(error, "Query references disallowed table(s): user_memories")

    def test_inline_comments_do_not_hide_table_references(self) -> None:
        sql = "SELECT * FROM users /* inline comment */ JOIN user_types ON users.user_type_id = user_types.id"

        self.assertEqual(referenced_sql_tables(sql), {"users", "user_types"})
        self.assertEqual(validate_sql_allowed_tables(sql), (True, ""))

    def test_encrypted_session_log_tables_are_readable_for_database_explorer(self) -> None:
        self.assertEqual(
            validate_sql_allowed_tables(
                "SELECT log_id, source, transcript_ciphertext FROM session_logs"
            ),
            (True, ""),
        )
        self.assertEqual(
            validate_sql_allowed_tables(
                "SELECT rating FROM session_log_feedback WHERE log_id = 'abc'"
            ),
            (True, ""),
        )


if __name__ == "__main__":
    unittest.main()
