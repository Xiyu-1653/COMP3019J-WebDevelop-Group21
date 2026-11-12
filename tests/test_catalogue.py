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
            self.assertEqual(queries.count_available_copies(cursor, 1), 2)
            self.assertEqual(queries.count_available_copies(cursor, 4), 1)

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
