"""Catalogue query tests against the shared MySQL database.

Requires a reachable MySQL database (``DATABASE_URL`` in ``.env``, or the
``DB_*`` environment variables). Run from the repo root:

    python -m unittest discover -s tests -v
"""

import os
import unittest

from pymysql.err import IntegrityError

from catalogue import queries
from common.db import connect


def _database_configured():
    return bool(os.environ.get("DATABASE_URL")) or "DB_PASSWORD" in os.environ


@unittest.skipUnless(_database_configured(), "No database configured; set DATABASE_URL")
class CatalogueQueryTests(unittest.TestCase):
    def test_connection(self):
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS one")
            self.assertEqual(cursor.fetchone()["one"], 1)

    def test_count_titles_matches_table(self):
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM title")
            expected = cursor.fetchone()["n"]
            self.assertEqual(queries.count_titles(cursor), expected)

    def test_get_all_titles_has_expected_shape(self):
        with connect() as connection, connection.cursor() as cursor:
            titles = queries.get_all_titles(cursor)
        self.assertIsInstance(titles, list)
        self.assertTrue(titles)
        for t in titles:
            for key in (
                "title_id", "isbn", "title", "author", "category",
                "available_copies", "total_copies",
            ):
                self.assertIn(key, t)
        # Newest first.
        created = [t["created_at"] for t in titles]
        self.assertEqual(created, sorted(created, reverse=True))

    def test_get_title(self):
        with connect() as connection, connection.cursor() as cursor:
            title = queries.get_title(cursor, 1)
        self.assertIsNotNone(title)
        self.assertEqual(title["title"], "Clean Code")
        self.assertEqual(title["author"], "Robert C. Martin")
        self.assertEqual(title["isbn"], "9780132350884")

    def test_get_title_missing_returns_none(self):
        with connect() as connection, connection.cursor() as cursor:
            self.assertIsNone(queries.get_title(cursor, 999999))

    def test_get_copies_for_title(self):
        with connect() as connection, connection.cursor() as cursor:
            copies = queries.get_copies_for_title(cursor, 1)
        self.assertEqual(len(copies), 3)
        self.assertEqual(
            {c["barcode"] for c in copies},
            {"KB-0001", "KB-0002", "KB-0003"},
        )

    def test_count_available_copies(self):
        with connect() as connection, connection.cursor() as cursor:
            for title_id in (1, 4):
                cursor.execute(
                    "SELECT COUNT(*) AS n FROM copy "
                    "WHERE title_id = %s AND status = 'available'",
                    (title_id,),
                )
                expected = cursor.fetchone()["n"]
                self.assertEqual(
                    queries.count_available_copies(cursor, title_id),
                    expected,
                )

    def test_seed_covers_all_copy_statuses(self):
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT DISTINCT status FROM copy")
            statuses = {row["status"] for row in cursor.fetchall()}
        self.assertSetEqual(
            statuses,
            {"available", "borrowed", "reserved", "damaged", "lost", "under_repair"},
        )

    def test_insert_copy_foreign_key_and_rollback(self):
        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO title (isbn, title, author, category) "
                    "VALUES ('0000000000000', 'Stage 1 Test Title', 'Test Author', 'Testing')"
                )
                title_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO copy (title_id, barcode, status, location) "
                    "VALUES (%s, 'KB-TEST-001', 'available', 'T-01-01')",
                    (title_id,),
                )

                copies = queries.get_copies_for_title(cursor, title_id)
                self.assertEqual(len(copies), 1)
                self.assertEqual(copies[0]["barcode"], "KB-TEST-001")
                self.assertEqual(queries.count_available_copies(cursor, title_id), 1)

                # Foreign key: a copy must reference an existing title.
                with self.assertRaises(IntegrityError):
                    cursor.execute(
                        "INSERT INTO copy (title_id, barcode, status) "
                        "VALUES (999999, 'KB-TEST-BAD', 'available')"
                    )
        finally:
            connection.rollback()
            connection.close()

    def test_get_categories_sorted_and_contains_computing(self):
        with connect() as connection, connection.cursor() as cursor:
            categories = queries.get_categories(cursor)
        self.assertIn("Computing", categories)
        self.assertEqual(categories, sorted(categories))

    def test_search_title_partial_match(self):
        with connect() as connection, connection.cursor() as cursor:
            rows = queries.search_titles(cursor, q="clean", field="title")
        self.assertTrue(rows)
        self.assertIn("Clean Code", {r["title"] for r in rows})

    def test_search_author_match(self):
        with connect() as connection, connection.cursor() as cursor:
            rows = queries.search_titles(cursor, q="austen", field="author")
        self.assertTrue(any("Pride and Prejudice" == r["title"] for r in rows))

    def test_search_isbn_ignores_hyphens(self):
        with connect() as connection, connection.cursor() as cursor:
            rows = queries.search_titles(cursor, q="978-0-13-235088-4", field="isbn")
        self.assertEqual([r["isbn"] for r in rows], ["9780132350884"])

    def test_search_combined_category_and_availability(self):
        with connect() as connection, connection.cursor() as cursor:
            rows = queries.search_titles(
                cursor, q="intelligence", field="all",
                category="Computing", available_only=True,
            )
        # AIMA has an available copy; the "all" search also hits author Russell.
        self.assertTrue(any("Modern Approach" in r["title"] for r in rows))
        self.assertTrue(all(r["category"] == "Computing" for r in rows))
        self.assertTrue(all(r["available_copies"] > 0 for r in rows))

    def test_availability_filter_excludes_titles_without_available_copy(self):
        with connect() as connection, connection.cursor() as cursor:
            all_rows = queries.search_titles(cursor, category="Computing", limit=1000)
            avail_rows = queries.search_titles(
                cursor, category="Computing", available_only=True, limit=1000,
            )
        all_ids = {r["title_id"] for r in all_rows}
        avail_ids = {r["title_id"] for r in avail_rows}
        self.assertLess(len(avail_ids), len(all_ids))
        self.assertTrue(avail_ids.issubset(all_ids))

    def test_count_titles_matching_agrees_with_search(self):
        with connect() as connection, connection.cursor() as cursor:
            total = queries.count_titles_matching(cursor, category="History")
            rows = queries.search_titles(cursor, category="History", limit=1000)
        self.assertEqual(total, len(rows))

    def test_recently_added_newest_first(self):
        with connect() as connection, connection.cursor() as cursor:
            rows = queries.get_recently_added(cursor, limit=6)
        self.assertEqual(len(rows), 6)
        created = [r["created_at"] for r in rows]
        self.assertEqual(created, sorted(created, reverse=True))

    def test_frequently_borrowed_counts_loans(self):
        with connect() as connection, connection.cursor() as cursor:
            rows = queries.get_frequently_borrowed(cursor, limit=10)
            cursor.execute(
                """
                SELECT t.title, COUNT(*) AS borrow_count
                FROM loan AS l
                JOIN copy AS c USING (copy_id)
                JOIN title AS t USING (title_id)
                GROUP BY t.title_id, t.title
                ORDER BY borrow_count DESC, t.title_id
                LIMIT 10
                """
            )
            expected = cursor.fetchall()
        self.assertTrue(rows)
        self.assertEqual(rows[0]["title"], expected[0]["title"])
        self.assertEqual(rows[0]["borrow_count"], expected[0]["borrow_count"])
        counts = [r["borrow_count"] for r in rows]
        self.assertEqual(counts, sorted(counts, reverse=True))
