"""Borrowing services called by the shared circulation desk."""

from common.db import connect
from borrow_return.fees import generate_overdue_fees
from reservation_management.allocation import allocate_available_copy

HISTORY_PAGE_SIZE = 10
READER_RESULT_LIMIT = 20

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


def desk_context(barcode="", reader_query="", page=1):
    """Find an item by barcode and return its desk page information."""
    barcode = barcode.strip()
    reader_query = reader_query.strip()
    try:
        page = max(1, int(page))
    except (ValueError, TypeError):
        page = 1
    context = {
        "barcode": barcode,
        "copy": None,
        "readers": [],
        "loans": [],
        "error": None,
        "reader_query": reader_query,
        "reader_limit_reached": False,
        "page": page,
        "total_pages": 1,
        "total_loans": 0,
    }
    if not barcode:
        return context
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(COPY_QUERY, (barcode,))
        copy = cursor.fetchone()
        if copy is None:
            context["error"] = "No item was found with that barcode."
            return context
        readers = []
        if reader_query:
            readers = find_readers(cursor, reader_query)
            context["reader_limit_reached"] = len(readers) > READER_RESULT_LIMIT
            readers = readers[:READER_RESULT_LIMIT]
        history_filter = "WHERE l.copy_id = %s"
        history_parameters = [copy["copy_id"]]
        if reader_query:
            reader_filter, reader_parameters = _reader_filter(reader_query)
            history_filter += " AND " + reader_filter
            history_parameters.extend(reader_parameters)
        cursor.execute(
            "SELECT COUNT(*) AS total "
            "FROM loan AS l JOIN user AS u ON u.user_id = l.reader_id "
            + history_filter,
            tuple(history_parameters),
        )
        total_loans = cursor.fetchone()["total"]
        total_pages = max(1, (total_loans + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        page = min(page, total_pages)
        offset = (page - 1) * HISTORY_PAGE_SIZE
        cursor.execute(
            """
            SELECT u.username, l.borrowed_at, l.due_at, l.returned_at
            FROM loan AS l JOIN user AS u ON u.user_id = l.reader_id
            """
            + history_filter
            + " ORDER BY l.loan_id DESC LIMIT %s OFFSET %s",
            tuple(history_parameters + [HISTORY_PAGE_SIZE, offset]),
        )
        loans = cursor.fetchall()
    context["copy"] = copy
    context["readers"] = readers
    context["loans"] = loans
    context["page"] = page
    context["total_pages"] = total_pages
    context["total_loans"] = total_loans
    return context


def _reader_filter(keyword):
    """Use the same reader search for checkout and loan history."""
    prefix = keyword.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
    condition = "(u.username LIKE %s ESCAPE '!'"
    parameters = [prefix]
    if keyword.isascii() and keyword.isdigit():
        condition += " OR u.user_id = %s"
        parameters.append(keyword)
    condition += ")"
    return condition, parameters


def find_readers(cursor, keyword):
    """Find readers by username prefix or exact user ID."""
    condition, parameters = _reader_filter(keyword)
    cursor.execute(
        "SELECT u.user_id, u.username, u.reader_category "
        "FROM user AS u WHERE u.role = 'reader' AND "
        + condition
        + " ORDER BY u.username, u.user_id LIMIT %s",
        tuple(parameters + [READER_RESULT_LIMIT + 1]),
    )
    return cursor.fetchall()


def _lock_copy(cursor, barcode):
    cursor.execute(
        "SELECT copy_id, title_id, status FROM copy WHERE barcode = %s FOR UPDATE",
        (barcode,),
    )
    copy = cursor.fetchone()
    if copy is None:
        raise DeskError("No item was found with that barcode.")
    return copy


def borrow(reader_id, barcode, librarian_id):
    """Issue an item and update its status in one transaction."""
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT user_id FROM user WHERE user_id = %s AND role = 'librarian'",
            (librarian_id,),
        )
        librarian = cursor.fetchone()
        if librarian is None:
            raise DeskError("A valid librarian account is required to issue an item.")
        copy = _lock_copy(cursor, barcode)
        _issue_loan(cursor, reader_id, librarian_id, copy)
        connection.commit()


def return_copy(barcode, reader_id=None):
    """Close the item's loan and update its status in one transaction."""
    with connect() as connection, connection.cursor() as cursor:
        copy = _lock_copy(cursor, barcode)
        if reader_id is not None:
            cursor.execute(
                "SELECT reader_id FROM loan WHERE copy_id = %s "
                "AND returned_at IS NULL FOR UPDATE", (copy["copy_id"],)
            )
            loan = cursor.fetchone()
            if loan is None or loan["reader_id"] != reader_id:
                raise DeskError("You can only return your own active loans.")
        reservation_id = _close_loan(cursor, copy)
        generate_overdue_fees(cursor, copy["copy_id"])
        connection.commit()
    return reservation_id


def _issue_loan(cursor, reader_id, librarian_id, copy):
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
        WHERE l.reader_id = %s AND l.returned_at IS NULL FOR UPDATE
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
        (reader_id, copy["copy_id"], librarian_id, days),
    )
    cursor.execute(
        "UPDATE copy SET status = 'borrowed' WHERE copy_id = %s",
        (copy["copy_id"],),
    )


def _close_loan(cursor, copy):
    if copy["status"] != "borrowed":
        raise DeskError("This item is not currently on loan.")
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

    # Allocation uses the same cursor so the return and reservation commit together.
    return allocate_available_copy(cursor, copy["copy_id"])


def self_borrow(reader_id, barcode):
    """Issue to the authenticated reader; NULL librarian means self-service."""
    with connect() as connection, connection.cursor() as cursor:
        copy = _lock_copy(cursor, barcode)
        _issue_loan(cursor, reader_id, None, copy)
        connection.commit()


def reader_desk_context(reader_id, query=""):
    """Search physical copies and show only this reader's active loans."""
    query = query.strip()
    copies = []
    with connect() as connection, connection.cursor() as cursor:
        if query:
            keyword = "%" + query.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
            cursor.execute(
                "SELECT c.barcode, c.status, c.location, t.title, t.author "
                "FROM copy AS c JOIN title AS t USING (title_id) "
                "WHERE c.barcode = %s OR t.title LIKE %s ESCAPE '!' "
                "OR t.author LIKE %s ESCAPE '!' "
                "ORDER BY (c.barcode = %s) DESC, t.title, c.barcode LIMIT 51",
                (query, keyword, keyword, query),
            )
            copies = cursor.fetchall()
        cursor.execute(
            "SELECT c.barcode, t.title, l.borrowed_at, l.due_at "
            "FROM loan AS l JOIN copy AS c USING (copy_id) "
            "JOIN title AS t USING (title_id) "
            "WHERE l.reader_id = %s AND l.returned_at IS NULL "
            "ORDER BY l.due_at, l.loan_id", (reader_id,),
        )
        loans = cursor.fetchall()
    return {"query": query, "copies": copies[:50], "truncated": len(copies) > 50,
            "loans": loans, "error": None}
