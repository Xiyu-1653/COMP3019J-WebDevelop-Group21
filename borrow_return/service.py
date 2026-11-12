"""Borrowing services called by the shared circulation desk."""

from common.db import connect

DEMO_BARCODE = "KB-0001"
DEMO_LIBRARIAN = 1
LOAN_RULES = {
    "undergraduate": (14, 5),
    "postgraduate": (30, 10),
    "teaching_staff": (60, 10),
}

COPY_QUERY = """
    SELECT c.copy_id, c.title_id, c.barcode, c.status, t.title
    FROM copy AS c JOIN title AS t USING (title_id)
    WHERE c.barcode = %s
"""


class DeskError(Exception):
    """A business rule prevented the requested operation."""


def desk_context():
    """Return the current demo item, readers and its loan history."""
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(COPY_QUERY, (DEMO_BARCODE,))
        copy = cursor.fetchone()
        if copy is None:
            raise DeskError(f"Demo item {DEMO_BARCODE} was not found in the database.")
        cursor.execute(
            "SELECT user_id, username, reader_category FROM user "
            "WHERE role = 'reader' ORDER BY username"
        )
        readers = cursor.fetchall()
        cursor.execute(
            """
            SELECT u.username, l.borrowed_at, l.due_at, l.returned_at
            FROM loan AS l JOIN user AS u ON u.user_id = l.reader_id
            WHERE l.copy_id = %s ORDER BY l.loan_id DESC
            """,
            (copy["copy_id"],),
        )
        loans = cursor.fetchall()
    return {"copy": copy, "readers": readers, "loans": loans}


def _lock_copy(cursor, barcode):
    cursor.execute(
        "SELECT copy_id, title_id, status FROM copy WHERE barcode = %s FOR UPDATE",
        (barcode,),
    )
    copy = cursor.fetchone()
    if copy is None:
        raise DeskError("No item was found with that barcode.")
    return copy


def borrow(reader_id, barcode):
    """Issue an item and update its status in one transaction."""
    with connect() as connection, connection.cursor() as cursor:
        copy = _lock_copy(cursor, barcode)
        _issue_loan(cursor, reader_id, copy)
        connection.commit()


def return_copy(barcode):
    """Close the item's loan and update its status in one transaction."""
    with connect() as connection, connection.cursor() as cursor:
        copy = _lock_copy(cursor, barcode)
        _close_loan(cursor, copy)
        connection.commit()


def _issue_loan(cursor, reader_id, copy):
    cursor.execute(
        "SELECT reader_category FROM user "
        "WHERE user_id = %s AND role = 'reader' FOR UPDATE",
        (reader_id,),
    )
    reader = cursor.fetchone()
    if reader is None:
        raise DeskError("Please select a valid reader.")
    if copy["status"] != "available":
        raise DeskError("This item is currently unavailable for checkout.")

    cursor.execute(
        """
        SELECT c.title_id, l.due_at < NOW() AS overdue
        FROM loan AS l JOIN copy AS c USING (copy_id)
        WHERE l.reader_id = %s AND l.returned_at IS NULL
        """,
        (reader_id,),
    )
    active_loans = cursor.fetchall()
    if any(loan["overdue"] for loan in active_loans):
        raise DeskError("This reader has overdue loans and cannot borrow another item.")

    cursor.execute(
        """
        SELECT 1 FROM fee AS f JOIN loan AS l USING (loan_id)
        WHERE l.reader_id = %s AND f.status = 'unpaid' LIMIT 1
        """,
        (reader_id,),
    )
    if cursor.fetchone():
        raise DeskError("This reader has unpaid fees and cannot borrow another item.")

    days, limit = LOAN_RULES[reader["reader_category"]]
    active_titles = {loan["title_id"] for loan in active_loans}
    if len(active_titles | {copy["title_id"]}) > limit:
        raise DeskError(f"This reader has reached the borrowing limit of {limit} distinct titles.")

    cursor.execute(
        """
        INSERT INTO loan (reader_id, copy_id, librarian_id, due_at)
        VALUES (%s, %s, %s, DATE_ADD(NOW(), INTERVAL %s DAY))
        """,
        (reader_id, copy["copy_id"], DEMO_LIBRARIAN, days),
    )
    cursor.execute(
        "UPDATE copy SET status = 'borrowed' WHERE copy_id = %s",
        (copy["copy_id"],),
    )


def _close_loan(cursor, copy):
    if copy["status"] != "borrowed":
        raise DeskError("This item is not currently on loan.")
    cursor.execute(
        "SELECT 1 FROM reservation WHERE title_id = %s AND status = 'waiting' LIMIT 1",
        (copy["title_id"],),
    )
    if cursor.fetchone():
        raise DeskError("This title has a waiting reservation. Its return requires reservation processing.")
    cursor.execute(
        """
        UPDATE loan SET returned_at = NOW()
        WHERE copy_id = %s AND returned_at IS NULL
        """,
        (copy["copy_id"],),
    )
    if cursor.rowcount != 1:
        raise DeskError("No active loan was found for this item.")
    cursor.execute(
        "UPDATE copy SET status = 'available' WHERE copy_id = %s",
        (copy["copy_id"],),
    )

