"""Generate one fixed overdue fee per loan and query fee records."""

from decimal import Decimal, InvalidOperation

from common.db import connect


def _overdue_fee_amount(cursor):
    """Read and validate the configured fixed charge."""
    cursor.execute(
        "SELECT config_value FROM system_config WHERE config_key = 'overdue_fee_amount'"
    )
    config = cursor.fetchone()
    if config is None:
        raise ValueError("Missing overdue_fee_amount configuration.")
    try:
        amount = Decimal(config["config_value"])
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("The overdue fee amount must be a valid number.") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("The overdue fee amount must be zero or greater.")

    return amount


def generate_overdue_fees(cursor, copy_id=None):
    """Generate missing fees using the caller's transaction."""
    amount = _overdue_fee_amount(cursor)
    query = """
        INSERT INTO fee (loan_id, amount, reason, status)
        SELECT l.loan_id, %s, 'overdue', 'unpaid'
        FROM loan AS l
        LEFT JOIN fee AS existing
            ON existing.loan_id = l.loan_id AND existing.reason = 'overdue'
        WHERE existing.fee_id IS NULL
          AND (
              (l.returned_at IS NULL AND l.due_at < NOW())
              OR l.returned_at > l.due_at
          )
    """
    parameters = [amount]
    if copy_id is not None:
        query += " AND l.copy_id = %s"
        parameters.append(copy_id)

    # The unique (loan_id, reason) key also protects simultaneous requests.
    # An existing charge keeps its original amount and payment status.
    query += " ON DUPLICATE KEY UPDATE fee_id = fee.fee_id"
    cursor.execute(query, tuple(parameters))


def generate_all_overdue_fees():
    with connect() as connection, connection.cursor() as cursor:
        generate_overdue_fees(cursor)
        connection.commit()


def load_overdue_loans():
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT l.loan_id, u.username, t.title, c.barcode,
                   l.due_at, l.returned_at, f.amount, f.status AS fee_status
            FROM loan AS l
            JOIN user AS u ON u.user_id = l.reader_id
            JOIN copy AS c USING (copy_id)
            JOIN title AS t USING (title_id)
            LEFT JOIN fee AS f ON f.loan_id = l.loan_id AND f.reason = 'overdue'
            WHERE (l.returned_at IS NULL AND l.due_at < NOW())
               OR l.returned_at > l.due_at
            ORDER BY l.due_at, l.loan_id
            """
        )
        return cursor.fetchall()


def load_reader_fees(reader_id):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT f.fee_id, f.loan_id, t.title, c.barcode, f.amount,
                   f.reason, f.status, f.created_at
            FROM fee AS f
            JOIN loan AS l USING (loan_id)
            JOIN copy AS c USING (copy_id)
            JOIN title AS t USING (title_id)
            WHERE l.reader_id = %s
            ORDER BY f.created_at DESC, f.fee_id DESC
            """,
            (reader_id,),
        )
        return cursor.fetchall()


def load_fee_summary(reader_id):
    """Return the fee policy and this reader's recorded unpaid balance."""
    with connect() as connection, connection.cursor() as cursor:
        overdue_amount = _overdue_fee_amount(cursor)
        cursor.execute(
            """
            SELECT COUNT(*) AS unpaid_count,
                   COALESCE(SUM(f.amount), 0) AS unpaid_total
            FROM fee AS f JOIN loan AS l USING (loan_id)
            WHERE l.reader_id = %s AND f.status = 'unpaid'
            """,
            (reader_id,),
        )
        summary = cursor.fetchone()
    summary["overdue_amount"] = overdue_amount
    return summary
