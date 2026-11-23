"""Reader loan queries and renewal rules, adapted from the account module."""

from common.db import connect
from borrow_return.service import LOAN_RULES, _lock_copy

LOAN_QUERY = """
    SELECT
        l.loan_id,
        l.borrowed_at,
        l.due_at,
        l.returned_at,
        l.renewal_count,
        (l.returned_at IS NULL AND l.due_at <= NOW()) AS overdue,
        EXISTS (
            SELECT 1 FROM reservation AS r
            WHERE r.title_id = t.title_id AND r.status = 'waiting'
        ) AS reserved,
        c.barcode,
        t.title_id,
        t.title,
        t.author
    FROM loan AS l
    JOIN copy AS c USING (copy_id)
    JOIN title AS t USING (title_id)
    WHERE l.reader_id = %s
    ORDER BY (l.returned_at IS NULL) DESC, l.due_at ASC, l.loan_id DESC
"""


class AccountError(Exception):
    """A personal-account action was refused by a business rule."""


def _decorate_loan(row):
    item = dict(row)
    item["overdue"] = bool(item.get("overdue"))
    item["reserved"] = bool(item.get("reserved"))
    item["renewal_count"] = int(item.get("renewal_count") or 0)
    can_renew, reason = _renewal_state(item)
    item["can_renew"] = can_renew
    item["renew_blocked_reason"] = reason
    return item


def _renewal_state(item):
    if item.get("returned_at") is not None:
        return False, "Returned loans cannot be renewed."
    if item.get("overdue"):
        return False, "Overdue loans cannot be renewed."
    if item.get("renewal_count"):
        return False, "This loan has already been renewed once."
    if item.get("reserved"):
        return False, "This title has a waiting reservation."
    return True, ""


def get_reader_loans(cursor, reader_id):
    """Return ``(current, history)`` loan rows for one reader only."""
    cursor.execute(LOAN_QUERY, (reader_id,))
    current = []
    history = []
    for row in cursor.fetchall() or ():
        item = _decorate_loan(row)
        if item["returned_at"] is None:
            current.append(item)
        else:
            history.append(item)
    return current, history


def load_reader_loans(reader_id):
    with connect() as connection, connection.cursor() as cursor:
        return get_reader_loans(cursor, reader_id)


def renew_loan_for_reader(cursor, loan_id, reader_id, reader_category):
    """Extend an open loan once. Raises LookupError if it is not this reader's."""
    cursor.execute(
        """
        SELECT c.barcode
        FROM loan AS l JOIN copy AS c USING (copy_id)
        WHERE l.loan_id = %s AND l.reader_id = %s
        """,
        (loan_id, reader_id),
    )
    item = cursor.fetchone()
    if item is None:
        raise LookupError("loan is not owned by this reader")
    _lock_copy(cursor, item["barcode"])

    cursor.execute(
        """
        SELECT
            l.loan_id,
            l.reader_id,
            l.due_at,
            l.returned_at,
            l.renewal_count,
            c.title_id,
            (l.returned_at IS NULL AND l.due_at <= NOW()) AS overdue
        FROM loan AS l
        JOIN copy AS c USING (copy_id)
        WHERE l.loan_id = %s
        FOR UPDATE
        """,
        (loan_id,),
    )
    loan = cursor.fetchone()
    if loan is None or int(loan["reader_id"]) != int(reader_id):
        raise LookupError("loan is not owned by this reader")

    cursor.execute(
        "SELECT 1 FROM reservation WHERE title_id = %s AND status = 'waiting' LIMIT 1 FOR UPDATE",
        (loan["title_id"],),
    )
    can_renew, reason = _renewal_state(
        {
            "returned_at": loan["returned_at"],
            "overdue": bool(loan["overdue"]),
            "renewal_count": int(loan["renewal_count"] or 0),
            "reserved": cursor.fetchone() is not None,
        }
    )
    if not can_renew:
        raise AccountError(reason)

    try:
        days = LOAN_RULES[reader_category][0]
    except (KeyError, TypeError, IndexError):
        raise AccountError("Your account does not have a borrowing period.") from None

    cursor.execute(
        """
        UPDATE loan
        SET due_at = DATE_ADD(due_at, INTERVAL %s DAY),
            renewal_count = 1
        WHERE loan_id = %s
          AND reader_id = %s
          AND returned_at IS NULL
          AND renewal_count = 0
          AND due_at > NOW()
        """,
        (days, loan_id, reader_id),
    )
    if cursor.rowcount != 1:
        raise AccountError("This loan could not be renewed.")
    return days


def load_renew_loan(loan_id, reader_id, reader_category):
    with connect() as connection, connection.cursor() as cursor:
        days = renew_loan_for_reader(cursor, loan_id, reader_id, reader_category)
        connection.commit()
        return days
