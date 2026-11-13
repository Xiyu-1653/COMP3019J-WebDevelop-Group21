"""FIFO queries for waiting reservations."""


def get_waiting_queue(cursor, title_id):
    """Return waiting reservations for a title, oldest first."""
    cursor.execute(
        """
        SELECT r.reservation_id, r.reader_id, u.username, u.reader_category,
               r.title_id, r.reserved_at
        FROM reservation AS r
        JOIN user AS u ON u.user_id = r.reader_id
        WHERE r.title_id = %s AND r.status = 'waiting'
        ORDER BY r.reserved_at, r.reservation_id
        """,
        (title_id,),
    )
    return cursor.fetchall()


def find_waiting_queues(cursor, keyword, limit=50):
    """Return titles whose name matches keyword, each with its waiting queue."""
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    cursor.execute(
        """
        SELECT title_id, title, author
        FROM title
        WHERE title LIKE %s
        ORDER BY title, title_id
        LIMIT %s
        """,
        (f"%{escaped}%", limit),
    )
    results = cursor.fetchall()
    for title in results:
        title["queue_rows"] = get_waiting_queue(cursor, title["title_id"])
    return results


def get_reader_reservations(cursor, reader_id):
    """Return a reader's reservations, open ones first, with queue positions."""
    cursor.execute(
        """
        SELECT r.reservation_id, r.title_id, t.title, t.author,
               r.status, r.reserved_at, r.collect_deadline,
               CASE
                   WHEN r.status = 'waiting' THEN (
                       SELECT COUNT(*) + 1
                       FROM reservation AS ahead
                       WHERE ahead.title_id = r.title_id
                         AND ahead.status = 'waiting'
                         AND (ahead.reserved_at < r.reserved_at
                              OR (ahead.reserved_at = r.reserved_at
                                  AND ahead.reservation_id < r.reservation_id))
                   )
                   ELSE NULL
               END AS queue_position
        FROM reservation AS r
        JOIN title AS t ON t.title_id = r.title_id
        WHERE r.reader_id = %s
        ORDER BY (r.status IN ('waiting', 'ready')) DESC,
                 r.reserved_at DESC, r.reservation_id DESC
        """,
        (reader_id,),
    )
    return cursor.fetchall()


def get_first_waiting_reservation(cursor, title_id, lock=False):
    """Return the FIFO queue head, optionally locking it for an update."""
    query = """
        SELECT reservation_id, reader_id
        FROM reservation
        WHERE title_id = %s AND status = 'waiting'
        ORDER BY reserved_at, reservation_id
        LIMIT 1
    """
    if lock:
        query += " FOR UPDATE"
    cursor.execute(query, (title_id,))
    return cursor.fetchone()
