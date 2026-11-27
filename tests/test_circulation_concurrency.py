"""Opt-in real MySQL contention test using isolated, disposable fixture rows."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from common.db import connect
from borrow_return import service


@unittest.skipUnless(os.environ.get('RUN_CIRCULATION_DB_TESTS') == '1',
                     'Set RUN_CIRCULATION_DB_TESTS=1 after applying 04_self_service.sql')
class CirculationConcurrencyTests(unittest.TestCase):
    def test_two_readers_compete_for_last_copy(self):
        token = uuid4().hex[:16]
        readers = []
        title_id = copy_id = None
        barcode = 'race-' + token
        try:
            with connect() as connection, connection.cursor() as cursor:
                for suffix in ['a', 'b']:
                    cursor.execute(
                        "INSERT INTO user (username, password_hash, role, reader_category) "
                        "VALUES (%s, 'test-only', 'reader', 'undergraduate')", (token + suffix,))
                    readers.append(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO title (isbn, title, author, category) VALUES (%s, %s, 'Test', 'Test')",
                    (token, 'Concurrency fixture ' + token))
                title_id = cursor.lastrowid
                cursor.execute("INSERT INTO copy (title_id, barcode) VALUES (%s, %s)", (title_id, barcode))
                copy_id = cursor.lastrowid
                connection.commit()
            barrier = Barrier(2)

            def borrow(reader):
                barrier.wait(timeout=10)
                try:
                    service.self_borrow(reader, barcode)
                    return 'issued'
                except service.DeskError:
                    return 'unavailable'

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(borrow, readers))
            self.assertCountEqual(results, ['issued', 'unavailable'])
            with connect() as connection, connection.cursor() as cursor:
                cursor.execute('SELECT reader_id FROM loan WHERE copy_id = %s AND returned_at IS NULL', (copy_id,))
                loans = cursor.fetchall()
                self.assertEqual(len(loans), 1)
                winner = loans[0]['reader_id']
                loser = next(reader for reader in readers if reader != winner)
            with self.assertRaises(service.DeskError):
                service.return_copy(barcode, reader_id=loser)
            service.return_copy(barcode, reader_id=winner)
            with connect() as connection, connection.cursor() as cursor:
                cursor.execute('SELECT status FROM copy WHERE copy_id = %s', (copy_id,))
                self.assertEqual(cursor.fetchone()['status'], 'available')
                cursor.execute('SELECT COUNT(*) AS n FROM loan WHERE copy_id = %s AND returned_at IS NULL', (copy_id,))
                self.assertEqual(cursor.fetchone()['n'], 0)
        finally:
            with connect() as connection, connection.cursor() as cursor:
                if copy_id is not None:
                    cursor.execute('DELETE FROM fee WHERE loan_id IN (SELECT loan_id FROM loan WHERE copy_id = %s)', (copy_id,))
                    cursor.execute('DELETE FROM loan WHERE copy_id = %s', (copy_id,))
                    cursor.execute('DELETE FROM copy WHERE copy_id = %s', (copy_id,))
                if title_id is not None:
                    cursor.execute('DELETE FROM title WHERE title_id = %s', (title_id,))
                for reader in readers:
                    cursor.execute('DELETE FROM user WHERE user_id = %s', (reader,))
                connection.commit()
