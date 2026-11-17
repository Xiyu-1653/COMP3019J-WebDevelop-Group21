"""My loans: reader isolation and the HTTP wiring around it.

Boundaries (Flask tutorial test_blog + LibraryOS smoke):
- login_required / role_required before any query
- the SQL is parameterized and filtered by session user_id
- current vs returned rows, overdue only while still open
- renewal, fees and notices stay unimplemented stubs
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app import create_app
from app.blueprints import account


def _loan(**overrides):
    row = {
        "loan_id": 1,
        "borrowed_at": datetime(2026, 11, 1, 10, 0),
        "due_at": datetime(2026, 11, 15, 10, 0),
        "returned_at": None,
        "renewal_count": 0,
        "overdue": 1,
        "barcode": "KB-0002",
        "title_id": 1,
        "title": "Clean Code",
        "author": "Robert C. Martin",
    }
    row.update(overrides)
    return row


class LoanQueryTests(unittest.TestCase):
    def test_query_filters_by_reader_id_parameter(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        account.get_reader_loans(cursor, 2)
        sql, params = cursor.execute.call_args.args
        self.assertIn("reader_id = %s", sql)
        self.assertNotIn("{", sql)
        self.assertEqual(params, (2,))

    def test_open_and_returned_rows_are_split(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _loan(),
            _loan(
                loan_id=5,
                title="Pride and Prejudice",
                barcode="KB-0007",
                overdue=0,
                returned_at=datetime(2026, 8, 20, 16, 0),
            ),
        ]
        current, history = account.get_reader_loans(cursor, 2)
        self.assertEqual([row["title"] for row in current], ["Clean Code"])
        self.assertEqual([row["title"] for row in history], ["Pride and Prejudice"])
        self.assertTrue(current[0]["overdue"])
        self.assertFalse(history[0]["overdue"])

    def test_returned_loan_is_not_overdue_even_if_flag_set(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _loan(overdue=1, returned_at=datetime(2026, 8, 20, 16, 0), title="Old")
        ]
        current, history = account.get_reader_loans(cursor, 2)
        self.assertEqual(current, [])
        self.assertEqual(history[0]["title"], "Old")


class LoanRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-only")
        self.client = self.app.test_client()
        self.guard = patch(
            "pymysql.connect",
            side_effect=AssertionError("Tests must not access shared database"),
        )
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def login_session(self, role="reader", user_id=2, username="alice"):
        with self.client.session_transaction() as session:
            session.update(
                user_id=user_id,
                username=username,
                role=role,
                reader_category="undergraduate" if role == "reader" else None,
            )

    def test_anonymous_my_loans_redirects_to_login(self):
        with patch.object(account, "load_reader_loans") as load:
            response = self.client.get("/my/loans")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)
        load.assert_not_called()

    def test_librarian_is_sent_away_from_my_loans(self):
        self.login_session(role="librarian", user_id=1, username="librarian")
        with patch.object(account, "load_reader_loans") as load:
            response = self.client.get("/my/loans")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/desk"))
        load.assert_not_called()

    def test_page_lists_only_the_session_reader_loans(self):
        self.login_session(user_id=2, username="alice")
        current, history = (
            [_loan()],
            [
                _loan(
                    loan_id=5,
                    title="Pride and Prejudice",
                    barcode="KB-0007",
                    overdue=0,
                    returned_at=datetime(2026, 8, 20, 16, 0),
                )
            ],
        )
        with patch.object(
            account, "load_reader_loans", return_value=(current, history)
        ) as load:
            response = self.client.get("/my/loans")
        self.assertEqual(response.status_code, 200)
        load.assert_called_once_with(2)
        body = response.get_data(as_text=True)
        self.assertIn("Clean Code", body)
        self.assertIn("Pride and Prejudice", body)
        self.assertIn("Overdue", body)
        self.assertIn("KB-0002", body)
        self.assertNotIn("Introduction to Algorithms", body)
        self.assertNotIn("bob", body.lower())

    def test_empty_loans_show_reader_facing_copy(self):
        self.login_session()
        with patch.object(account, "load_reader_loans", return_value=([], [])):
            response = self.client.get("/my/loans")
        body = response.get_data(as_text=True)
        self.assertIn("You have no books on loan.", body)
        self.assertIn("You have no past loans.", body)

    def test_database_error_is_shown_without_crashing(self):
        self.login_session()
        with patch.object(
            account, "load_reader_loans", side_effect=RuntimeError("unavailable")
        ):
            response = self.client.get("/my/loans")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Could not load your loans: unavailable", response.get_data(as_text=True))

    def test_renewal_stays_unimplemented_and_reader_only(self):
        self.login_session()
        response = self.client.post("/loans/1/renew")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/my/loans"))
        with self.client.session_transaction() as session:
            messages = [text for _category, text in session["_flashes"]]
        self.assertIn("Renewal is not implemented yet.", messages)

        self.login_session(role="librarian", user_id=1, username="librarian")
        response = self.client.post("/loans/1/renew")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/desk"))
