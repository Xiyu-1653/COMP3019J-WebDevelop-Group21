"""Read-only catalogue queries for the ``title`` and ``copy`` tables.

Functions follow the project convention used by ``reservation_management``:
each one receives an open ``DictCursor`` and returns plain dicts. The caller
owns the connection and any transaction, so these functions never open or
close connections themselves.
"""

from __future__ import annotations

import re

_TITLE_AGGREGATE_SELECT = """
    SELECT t.title_id, t.isbn, t.title, t.author, t.category,
           t.description, t.has_digital_version, t.created_at,
           t.cover_url,
           COALESCE(SUM(c.status = 'available'), 0) AS available_copies,
           COUNT(c.copy_id) AS total_copies
    FROM title AS t
    LEFT JOIN copy AS c USING (title_id)
"""


def get_all_titles(cursor):
    """Return every title with its copy counts, newest first."""
    cursor.execute(
        _TITLE_AGGREGATE_SELECT
        + " GROUP BY t.title_id ORDER BY t.created_at DESC, t.title_id DESC"
    )
    return cursor.fetchall()


def get_title(cursor, title_id):
    """Return one title with its copy counts, or ``None`` if it does not exist."""
    cursor.execute(
        _TITLE_AGGREGATE_SELECT + " WHERE t.title_id = %s GROUP BY t.title_id",
        (title_id,),
    )
    return cursor.fetchone()


def get_copies_for_title(cursor, title_id):
    """Return every physical copy belonging to a title, ordered by copy_id."""
    cursor.execute(
        "SELECT copy_id, title_id, barcode, status, location "
        "FROM copy WHERE title_id = %s ORDER BY copy_id",
        (title_id,),
    )
    return cursor.fetchall()


def count_available_copies(cursor, title_id):
    """Return the number of copies of a title currently available to borrow.

    Only ``available`` copies count; ``reserved``, ``borrowed``, ``damaged``,
    ``lost`` and ``under_repair`` copies are not available.
    """
    cursor.execute(
        "SELECT COUNT(*) AS available_copies FROM copy "
        "WHERE title_id = %s AND status = 'available'",
        (title_id,),
    )
    row = cursor.fetchone()
    return row["available_copies"] if row else 0


def count_titles(cursor):
    """Return the total number of titles in the catalogue."""
    cursor.execute("SELECT COUNT(*) AS total FROM title")
    return cursor.fetchone()["total"]


# ---------------------------------------------------------------------------
# Browse helpers used by the catalogue page and homepage.
# ---------------------------------------------------------------------------

_SEARCH_FIELDS = ("all", "title", "author", "isbn")


def get_categories(cursor):
    """Return the distinct catalogue categories, sorted alphabetically."""
    cursor.execute("SELECT DISTINCT category FROM title ORDER BY category")
    return [row["category"] for row in cursor.fetchall()]


def get_recently_added(cursor, limit=6):
    """Return the most recently added titles, newest first."""
    cursor.execute(
        _TITLE_AGGREGATE_SELECT
        + " GROUP BY t.title_id ORDER BY t.created_at DESC, t.title_id DESC LIMIT %s",
        (limit,),
    )
    return cursor.fetchall()


def get_frequently_borrowed(cursor, limit=6):
    """Return titles ordered by number of loan records, most borrowed first.

    Reads the shared ``loan`` table owned by the Borrowing module: every loan
    row links to its title through ``copy``, so the borrowing frequency of a
    title is ``COUNT(loan.loan_id)``. Returns an empty list when there are no
    loan records (rather than inventing statistics).
    """
    cursor.execute(
        """
        SELECT t.title_id, t.title, t.author, t.category, t.cover_url,
               COUNT(l.loan_id) AS borrow_count
        FROM loan AS l
        JOIN copy AS c ON c.copy_id = l.copy_id
        JOIN title AS t ON t.title_id = c.title_id
        GROUP BY t.title_id
        ORDER BY borrow_count DESC, t.title_id
        LIMIT %s
        """,
        (limit,),
    )
    return cursor.fetchall()


def _escape_like(value):
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalise_isbn(value):
    """Remove spaces and hyphens so ISBN-10/ISBN-13 variants match one field."""
    return re.sub(r"[\s-]+", "", value)


def _build_filters(q=None, field="all", category=None, available_only=False):
    """Build a parameterised WHERE clause plus its parameters.

    Every value is passed as a query parameter (never interpolated), and user
    ``%``/``_`` characters are escaped so they match literally.
    """
    clauses = []
    params = []
    if q:
        if field == "isbn":
            term = _normalise_isbn(q)
        else:
            term = q
        pattern = f"%{_escape_like(term)}%"
        if field == "title":
            clauses.append("t.title LIKE %s")
            params.append(pattern)
        elif field == "author":
            clauses.append("t.author LIKE %s")
            params.append(pattern)
        elif field == "isbn":
            clauses.append("t.isbn LIKE %s")
            params.append(pattern)
        else:  # "all": title, author or ISBN
            clauses.append(
                "(t.title LIKE %s OR t.author LIKE %s OR t.isbn LIKE %s)"
            )
            params.extend([pattern, pattern, pattern])
    if category:
        clauses.append("t.category = %s")
        params.append(category)
    if available_only:
        clauses.append(
            "EXISTS (SELECT 1 FROM copy AS av "
            "WHERE av.title_id = t.title_id AND av.status = 'available')"
        )
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def search_titles(
    cursor,
    *,
    q=None,
    field="all",
    category=None,
    available_only=False,
    limit=12,
    offset=0,
):
    """Return one page of titles matching the search and filter conditions."""
    where, params = _build_filters(q, field, category, available_only)
    cursor.execute(
        _TITLE_AGGREGATE_SELECT
        + where
        + " GROUP BY t.title_id"
        + " ORDER BY t.created_at DESC, t.title_id DESC"
        + " LIMIT %s OFFSET %s",
        params + [limit, offset],
    )
    return cursor.fetchall()


def count_titles_matching(
    cursor, *, q=None, field="all", category=None, available_only=False
):
    """Return the number of titles matching the search and filter conditions."""
    where, params = _build_filters(q, field, category, available_only)
    cursor.execute("SELECT COUNT(*) AS total FROM title AS t" + where, params)
    return cursor.fetchone()["total"]
