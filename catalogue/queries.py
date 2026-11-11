"""Read-only catalogue queries for the ``title`` and ``copy`` tables.

Functions follow the project convention used by ``reservation_management``:
each one receives an open ``DictCursor`` and returns plain dicts. The caller
owns the connection and any transaction, so these functions never open or
close connections themselves.
"""

from __future__ import annotations

_TITLE_AGGREGATE_SELECT = """
    SELECT t.title_id, t.isbn, t.title, t.author, t.category,
           t.description, t.has_digital_version, t.created_at,
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
