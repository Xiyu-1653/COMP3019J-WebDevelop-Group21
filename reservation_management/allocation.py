"""Allocate available copies to readers at the head of a FIFO queue."""

from .queue import get_first_waiting_reservation


def allocate_available_copy(cursor, copy_id):
    """Allocate an available copy; return its reservation ID or None.

    The caller owns the transaction and must commit or roll it back.
    """
    cursor.execute(
        "SELECT title_id, status FROM copy WHERE copy_id = %s FOR UPDATE",
        (copy_id,),
    )
    copy = cursor.fetchone()
    if copy is None or copy["status"] != "available":
        return None

    reservation = get_first_waiting_reservation(
        cursor, copy["title_id"], lock=True
    )
    if reservation is None:
        return None

    cursor.execute(
        "SELECT config_value FROM system_config "
        "WHERE config_key = 'collection_window_days'"
    )
    config = cursor.fetchone()
    if config is None:
        raise ValueError("Missing collection_window_days configuration.")

    cursor.execute(
        """
        UPDATE reservation
        SET status = 'ready', allocated_copy_id = %s,
            collect_deadline = DATE_ADD(NOW(), INTERVAL %s DAY)
        WHERE reservation_id = %s
        """,
        (copy_id, int(config["config_value"]), reservation["reservation_id"]),
    )
    cursor.execute(
        "UPDATE copy SET status = 'reserved' WHERE copy_id = %s", (copy_id,)
    )
    cursor.execute(
        """
        INSERT INTO notification (user_id, reservation_id, message)
        VALUES (%s, %s, %s)
        """,
        (
            reservation["reader_id"],
            reservation["reservation_id"],
            "Your reserved copy is ready for collection.",
        ),
    )
    return reservation["reservation_id"]
