"""Expire uncollected reservations and pass copies to the next reader."""

from .queue import get_first_waiting_reservation


def process_expired_reservations(cursor):
    """Expire overdue reservations and pass copies along in FIFO order.

    Returns the number expired. The caller owns the transaction.
    """
    cursor.execute(
        "SELECT config_value FROM system_config "
        "WHERE config_key = 'collection_window_days'"
    )
    config = cursor.fetchone()
    if config is None:
        raise ValueError("Missing collection_window_days configuration.")
    collection_days = int(config["config_value"])

    cursor.execute(
        """
        SELECT reservation_id, reader_id, title_id, allocated_copy_id
        FROM reservation
        WHERE status = 'ready' AND collect_deadline <= NOW()
        ORDER BY collect_deadline, reservation_id
        FOR UPDATE
        """
    )
    expired = cursor.fetchall()

    for reservation in expired:
        cursor.execute(
            """
            UPDATE reservation
            SET status = 'expired', allocated_copy_id = NULL,
                collect_deadline = NULL
            WHERE reservation_id = %s
            """,
            (reservation["reservation_id"],),
        )
        cursor.execute(
            """
            INSERT INTO notification (user_id, reservation_id, message)
            VALUES (%s, %s, %s)
            """,
            (
                reservation["reader_id"],
                reservation["reservation_id"],
                "Your reservation has expired because it was not collected in time.",
            ),
        )

        next_reservation = get_first_waiting_reservation(
            cursor, reservation["title_id"], lock=True
        )
        copy_id = reservation["allocated_copy_id"]
        if next_reservation is None:
            cursor.execute(
                "UPDATE copy SET status = 'available' WHERE copy_id = %s",
                (copy_id,),
            )
            continue

        cursor.execute(
            """
            UPDATE reservation
            SET status = 'ready', allocated_copy_id = %s,
                collect_deadline = DATE_ADD(NOW(), INTERVAL %s DAY)
            WHERE reservation_id = %s
            """,
            (copy_id, collection_days, next_reservation["reservation_id"]),
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
                next_reservation["reader_id"],
                next_reservation["reservation_id"],
                "Your reserved copy is ready for collection.",
            ),
        )

    return len(expired)
