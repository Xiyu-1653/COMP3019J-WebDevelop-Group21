"""FIFO queries for waiting reservations."""


def get_waiting_queue(cursor, title_id):
    """Return waiting reservations for a title, oldest first."""
    cursor.execute(
        """
        SELECT reservation_id, reader_id, title_id, reserved_at
        FROM reservation
        WHERE title_id = %s AND status = 'waiting'
        ORDER BY reserved_at, reservation_id
        """,
        (title_id,),
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
