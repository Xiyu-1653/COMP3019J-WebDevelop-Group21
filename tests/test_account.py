"""My loans, renewal ownership and fee history.

Boundaries (Flask tutorial test_blog author checks + LibraryOS smoke):
- login_required / role_required before any query
- SQL is parameterized and filtered by session user_id
- current vs returned rows; overdue only while still open
- renew only own, open, not overdue, not reserved, once
- other readers' loan_id is 403 and does not write
- fees list is read-only and isolated; payment stays unimplemented
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
        "due_at": datetime(2026, 11, 27, 10, 0),
        "returned_at": None,
        "renewal_count": 0,
        "overdue": 0,
        "reserved": 0,
        "barcode": "KB-0001",
        "title_id": 1,
        "title": "Clean Code",
        "author": "Robert C. Martin",
    }
    row.update(overrides)
    return row


def _open_loan_row(**overrides):
    row = {
        "loan_id": 10,
        "reader_id": 2,
        "due_at": datetime(2026, 11, 27, 10, 0),
        "returned_at": None,
        "renewal_count": 0,
        "title_id": 1,
        "overdue": 0,
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
            _loan(overdue=1, title="Clean Code"),
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
        self.assertFalse(current[0]["can_renew"])
        self.assertFalse(history[0]["overdue"])

    def test_returned_loan_is_not_overdue_even_if_flag_set(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _loan(overdue=1, returned_at=datetime(2026, 8, 20, 16, 0), title="Old")
        ]
        current, history = account.get_reader_loans(cursor, 2)
        self.assertEqual(current, [])
        self.assertEqual(history[0]["title"], "Old")

    def test_renew_button_only_for_eligible_open_loans(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _loan(loan_id=1),
            _loan(loan_id=2, overdue=1, title="Late"),
            _loan(loan_id=3, reserved=1, title="Held"),
            _loan(loan_id=4, renewal_count=1, title="Used"),
        ]
        current, _history = account.get_reader_loans(cursor, 2)
        by_id = {row["loan_id"]: row for row in current}
        self.assertTrue(by_id[1]["can_renew"])
        self.assertFalse(by_id[2]["can_renew"])
        self.assertFalse(by_id[3]["can_renew"])
        self.assertFalse(by_id[4]["can_renew"])


class RenewalRuleTests(unittest.TestCase):
    def _cursor(self, loan, waiting=None):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [loan, waiting]
        cursor.rowcount = 1
        return cursor

    def test_renew_rejects_other_reader_before_writing(self):
        cursor = self._cursor(_open_loan_row(reader_id=3))
        with self.assertRaises(LookupError):
            account.renew_loan_for_reader(cursor, 10, 2, "undergraduate")
        updates = [call for call in cursor.execute.call_args_list if "UPDATE loan" in call.args[0]]
        self.assertEqual(updates, [])

    def test_renew_rejects_missing_loan(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        with self.assertRaises(LookupError):
            account.renew_loan_for_reader(cursor, 999, 2, "undergraduate")

    def test_renew_rejects_overdue_already_renewed_and_reserved(self):
        cases = [
            (_open_loan_row(overdue=1), None, "Overdue"),
            (_open_loan_row(renewal_count=1), None, "already been renewed"),
            (_open_loan_row(), {"exists": 1}, "waiting reservation"),
            (_open_loan_row(returned_at=datetime(2026, 11, 20)), None, "Returned"),
        ]
        for loan, waiting, snippet in cases:
            with self.subTest(snippet=snippet):
                cursor = self._cursor(loan, waiting)
                with self.assertRaisesRegex(account.AccountError, snippet):
                    account.renew_loan_for_reader(cursor, 10, 2, "undergraduate")

    def test_successful_renew_uses_desk_loan_period(self):
        for category, days in [
            ("undergraduate", 14),
            ("postgraduate", 30),
            ("teaching_staff", 60),
        ]:
            with self.subTest(category=category):
                cursor = self._cursor(_open_loan_row())
                self.assertEqual(
                    account.renew_loan_for_reader(cursor, 10, 2, category),
                    days,
                )
                update = [call for call in cursor.execute.call_args_list if "UPDATE loan" in call.args[0]][0]
                self.assertIn("DATE_ADD(due_at, INTERVAL %s DAY)", update.args[0])
                self.assertIn("renewal_count = 1", update.args[0])
                self.assertEqual(update.args[1], (days, 10, 2))


class FeeQueryTests(unittest.TestCase):
    def test_fee_query_filters_by_reader_id(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        account.get_reader_fees(cursor, 3)
        sql, params = cursor.execute.call_args.args
        self.assertIn("reader_id = %s", sql)
        self.assertEqual(params, (3,))


class AccountRouteTests(unittest.TestCase):
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

    def login_session(self, role="reader", user_id=2, username="alice", category="undergraduate"):
        with self.client.session_transaction() as session:
            session.update(
                user_id=user_id,
                username=username,
                role=role,
                reader_category=category if role == "reader" else None,
            )

    def _flashes(self):
        with self.client.session_transaction() as session:
            return [text for _category, text in session.get("_flashes", [])]

    def test_anonymous_account_pages_redirect_to_login(self):
        for path in ("/my/loans", "/my/fees"):
            with self.subTest(path=path), patch.object(account, "load_reader_loans") as load:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.location)
                load.assert_not_called()

    def test_librarian_is_sent_away_from_reader_pages(self):
        self.login_session(role="librarian", user_id=1, username="librarian")
        for path in ("/my/loans", "/my/fees"):
            with self.subTest(path=path), patch.object(account, "load_reader_loans") as load:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.location.endswith("/desk"))
                load.assert_not_called()

    def test_page_lists_only_the_session_reader_loans(self):
        self.login_session(user_id=2, username="alice")
        current, history = (
            [_loan(overdue=1, barcode="KB-0002")],
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

    def test_renew_forwards_session_identity_and_reports_success(self):
        self.login_session(user_id=2, category="undergraduate")
        with patch.object(account, "load_renew_loan", return_value=14) as renew:
            response = self.client.post("/loans/10/renew")
        renew.assert_called_once_with(10, 2, "undergraduate")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/my/loans"))
        self.assertTrue(any("extended by 14 days" in text for text in self._flashes()))

    def test_renew_other_reader_is_forbidden(self):
        self.login_session(user_id=2)
        with patch.object(account, "load_renew_loan", side_effect=LookupError) as renew:
            response = self.client.post("/loans/2/renew")
        renew.assert_called_once_with(2, 2, "undergraduate")
        self.assertEqual(response.status_code, 403)

    def test_renew_rule_failure_is_flashed(self):
        self.login_session()
        with patch.object(
            account, "load_renew_loan", side_effect=account.AccountError("Overdue loans cannot be renewed.")
        ):
            response = self.client.post("/loans/1/renew")
        self.assertEqual(response.status_code, 302)
        self.assertIn("Overdue loans cannot be renewed.", self._flashes())

    def test_librarian_cannot_renew(self):
        self.login_session(role="librarian", user_id=1, username="librarian")
        with patch.object(account, "load_renew_loan") as renew:
            response = self.client.post("/loans/1/renew")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/desk"))
        renew.assert_not_called()

    def test_fees_page_lists_only_session_reader_rows(self):
        self.login_session(user_id=3, username="bob")
        rows = [
            {
                "fee_id": 1,
                "amount": "5.00",
                "reason": "overdue",
                "status": "unpaid",
                "created_at": datetime(2026, 10, 21),
                "loan_id": 2,
                "title_id": 2,
                "title": "Introduction to Algorithms",
            }
        ]
        with patch.object(account, "load_reader_fees", return_value=rows) as load:
            response = self.client.get("/my/fees")
        self.assertEqual(response.status_code, 200)
        load.assert_called_once_with(3)
        body = response.get_data(as_text=True)
        self.assertIn("Introduction to Algorithms", body)
        self.assertIn("Unpaid", body)
        self.assertNotIn("Clean Code", body)
        self.assertNotIn("You have no fees.", body)

    def test_empty_fees_show_reader_facing_copy(self):
        self.login_session()
        with patch.object(account, "load_reader_fees", return_value=[]):
            response = self.client.get("/my/fees")
        self.assertIn("You have no fees.", response.get_data(as_text=True))
