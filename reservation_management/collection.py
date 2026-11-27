"""Handle a reader collecting or cancelling a reservation."""

from .allocation import allocate_available_copy
from .expiration import process_expired_reservations


class ReservationError(Exception):
    """A reservation could not be collected or cancelled in its current state."""


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


def cancel_reservation(cursor, reservation_id, reader_id):
    """Cancel one of the reader's waiting or ready reservations.

    The caller owns the transaction. A ready reservation releases its copy:
    the copy is passed to the next waiting reservation, or becomes available.
    """
    cursor.execute(
        """
        SELECT reservation_id, reader_id, status, allocated_copy_id
        FROM reservation
        WHERE reservation_id = %s
        FOR UPDATE
        """,
        (reservation_id,),
    )
    reservation = cursor.fetchone()
    if reservation is None:
        raise ReservationError("That reservation does not exist.")
    if reservation["reader_id"] != reader_id:
        raise ReservationError("You can only cancel your own reservations.")
    if reservation["status"] not in ("waiting", "ready"):
        raise ReservationError("This reservation can no longer be cancelled.")

    copy_id = reservation["allocated_copy_id"]
    if copy_id is not None:
        cursor.execute(
            "SELECT status FROM copy WHERE copy_id = %s FOR UPDATE",
            (copy_id,),
        )
        copy = cursor.fetchone()
        if copy is None:
            raise ReservationError("The allocated copy no longer exists.")
        if copy["status"] != "reserved":
            raise ReservationError("The allocated copy is not reserved.")

    cursor.execute(
        """
        UPDATE reservation
        SET status = 'cancelled', allocated_copy_id = NULL,
            collect_deadline = NULL
        WHERE reservation_id = %s
        """,
        (reservation_id,),
    )

    if copy_id is not None:
        cursor.execute(
            "UPDATE copy SET status = 'available' WHERE copy_id = %s",
            (copy_id,),
        )
        allocate_available_copy(cursor, copy_id)
