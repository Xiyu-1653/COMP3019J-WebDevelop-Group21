"""Handle a reader collecting a reserved copy."""

from .expiration import process_expired_reservations


class ReservationError(Exception):
    """A reservation could not be collected in its current state."""


def collect_reservation(cursor, reservation_id, librarian_id, loan_days):
    """Create the loan and fulfil the reservation; return the loan ID.

    Overdue reservations are expired first. The caller owns the transaction.
    """
    process_expired_reservations(cursor)

    cursor.execute(
        """
        SELECT reader_id, allocated_copy_id
        FROM reservation
        WHERE reservation_id = %s AND status = 'ready'
        FOR UPDATE
        """,
        (reservation_id,),
    )
    reservation = cursor.fetchone()
    if reservation is None:
        raise ReservationError("This reservation is no longer ready for collection.")

    cursor.execute(
        """
        INSERT INTO loan (reader_id, copy_id, librarian_id, due_at)
        VALUES (%s, %s, %s, DATE_ADD(NOW(), INTERVAL %s DAY))
        """,
        (
            reservation["reader_id"],
            reservation["allocated_copy_id"],
            librarian_id,
            loan_days,
        ),
    )
    loan_id = cursor.lastrowid
    cursor.execute(
        """
        UPDATE reservation
        SET status = 'fulfilled', allocated_copy_id = NULL,
            collect_deadline = NULL
        WHERE reservation_id = %s
        """,
        (reservation_id,),
    )
    cursor.execute(
        "UPDATE copy SET status = 'borrowed' WHERE copy_id = %s",
        (reservation["allocated_copy_id"],),
    )
    return loan_id
