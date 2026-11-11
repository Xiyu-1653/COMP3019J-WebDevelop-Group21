"""Local demonstration of the Know Book circulation desk."""

from flask import Flask, redirect, render_template, request, url_for

from common.db import connect

app = Flask(__name__)
DEMO_BARCODE = "KB-0001"
DEMO_LIBRARIAN = 1
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


def desk_page(error=None):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(COPY_QUERY, (DEMO_BARCODE,))
        copy = cursor.fetchone()
        cursor.execute(
            "SELECT user_id, username, reader_category FROM user "
            "WHERE role = 'reader' ORDER BY username"
        )
        readers = cursor.fetchall()
        cursor.execute(
            """
            SELECT u.username, l.borrowed_at, l.due_at, l.returned_at
            FROM loan AS l JOIN user AS u ON u.user_id = l.reader_id
            WHERE l.copy_id = %s ORDER BY l.loan_id DESC
            """,
            (copy["copy_id"],),
        )
        loans = cursor.fetchall()
    return render_template(
        "desk.html", copy=copy, readers=readers, loans=loans, error=error,
        result=request.args.get("result"),
    )


@app.get("/")
def index():
    return desk_page()


def borrow(cursor, reader_id, copy):
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
        WHERE l.reader_id = %s AND l.returned_at IS NULL
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
        (reader_id, copy["copy_id"], DEMO_LIBRARIAN, days),
    )
    cursor.execute(
        "UPDATE copy SET status = 'borrowed' WHERE copy_id = %s",
        (copy["copy_id"],),
    )


def return_copy(cursor, copy):
    if copy["status"] != "borrowed":
        raise DeskError("This item is not currently on loan.")
    cursor.execute(
        "SELECT 1 FROM reservation WHERE title_id = %s AND status = 'waiting' LIMIT 1",
        (copy["title_id"],),
    )
    if cursor.fetchone():
        raise DeskError("This title has a waiting reservation. Its return requires reservation processing.")
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


@app.post("/desk")
def update_desk():
    action = request.form.get("action")
    if action not in {"borrow", "return"}:
        return desk_page("Unknown action."), 400

    try:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT copy_id, title_id, status FROM copy WHERE barcode = %s FOR UPDATE",
                (DEMO_BARCODE,),
            )
            copy = cursor.fetchone()
            if action == "borrow":
                borrow(cursor, request.form.get("reader_id", type=int), copy)
            else:
                return_copy(cursor, copy)
            connection.commit()
    except DeskError as error:
        # Closing the uncommitted connection rolls back the operation.
        return desk_page(str(error)), 409

    return redirect(url_for("index", result=action), code=303)
