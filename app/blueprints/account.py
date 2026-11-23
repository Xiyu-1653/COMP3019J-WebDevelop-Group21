"""User & Account Management: personal loan records and renewal."""

from flask import Blueprint, abort, flash, redirect, render_template, session, url_for

from app.blueprints.auth import login_required, role_required
from common.db import connect

try:
    from borrow_return.service import LOAN_RULES
except ImportError:
    LOAN_RULES = {
        "undergraduate": (14, 5),
        "postgraduate": (30, 10),
        "teaching_staff": (60, 10),
    }

account_bp = Blueprint("account", __name__)

LOAN_QUERY = """
    SELECT
        l.loan_id,
        l.borrowed_at,
        l.due_at,
        l.returned_at,
        l.renewal_count,
        (l.returned_at IS NULL AND l.due_at < NOW()) AS overdue,
        EXISTS (
            SELECT 1 FROM reservation AS r
            WHERE r.title_id = t.title_id AND r.status = 'waiting'
        ) AS reserved,
        c.barcode,
        t.title_id,
        t.title,
        t.author
    FROM loan AS l
    JOIN copy AS c USING (copy_id)
    JOIN title AS t USING (title_id)
    WHERE l.reader_id = %s
    ORDER BY (l.returned_at IS NULL) DESC, l.due_at ASC, l.loan_id DESC
"""

FEE_QUERY = """
    SELECT
        f.fee_id,
        f.amount,
        f.reason,
        f.status,
        f.created_at,
        l.loan_id,
        t.title_id,
        t.title
    FROM fee AS f
    JOIN loan AS l USING (loan_id)
    JOIN copy AS c USING (copy_id)
    JOIN title AS t USING (title_id)
    WHERE l.reader_id = %s
    ORDER BY f.created_at DESC, f.fee_id DESC
"""


class AccountError(Exception):
    """A personal-account action was refused by a business rule."""


def _decorate_loan(row):
    item = dict(row)
    item["overdue"] = bool(item.get("overdue"))
    item["reserved"] = bool(item.get("reserved"))
    item["renewal_count"] = int(item.get("renewal_count") or 0)
    can_renew, reason = _renewal_state(item)
    item["can_renew"] = can_renew
    item["renew_blocked_reason"] = reason
    return item


def _renewal_state(item):
    if item.get("returned_at") is not None:
        return False, "Returned loans cannot be renewed."
    if item.get("overdue"):
        return False, "Overdue loans cannot be renewed."
    if item.get("renewal_count"):
        return False, "This loan has already been renewed once."
    if item.get("reserved"):
        return False, "This title has a waiting reservation."
    return True, ""


def get_reader_loans(cursor, reader_id):
    """Return ``(current, history)`` loan rows for one reader only."""
    cursor.execute(LOAN_QUERY, (reader_id,))
    current = []
    history = []
    for row in cursor.fetchall() or ():
        item = _decorate_loan(row)
        if item["returned_at"] is None:
            current.append(item)
        else:
            history.append(item)
    return current, history


def load_reader_loans(reader_id):
    with connect() as connection, connection.cursor() as cursor:
        return get_reader_loans(cursor, reader_id)


def get_reader_fees(cursor, reader_id):
    """Return fee rows that belong to one reader only."""
    cursor.execute(FEE_QUERY, (reader_id,))
    return [dict(row) for row in cursor.fetchall() or ()]


def load_reader_fees(reader_id):
    with connect() as connection, connection.cursor() as cursor:
        return get_reader_fees(cursor, reader_id)


def renew_loan_for_reader(cursor, loan_id, reader_id, reader_category):
    """Extend an open loan once. Raises LookupError if it is not this reader's."""
    cursor.execute(
        """
        SELECT
            l.loan_id,
            l.reader_id,
            l.due_at,
            l.returned_at,
            l.renewal_count,
            c.title_id,
            (l.returned_at IS NULL AND l.due_at < NOW()) AS overdue
        FROM loan AS l
        JOIN copy AS c USING (copy_id)
        WHERE l.loan_id = %s
        FOR UPDATE
        """,
        (loan_id,),
    )
    loan = cursor.fetchone()
    if loan is None or int(loan["reader_id"]) != int(reader_id):
        raise LookupError("loan is not owned by this reader")

    cursor.execute(
        "SELECT 1 FROM reservation WHERE title_id = %s AND status = 'waiting' LIMIT 1",
        (loan["title_id"],),
    )
    can_renew, reason = _renewal_state(
        {
            "returned_at": loan["returned_at"],
            "overdue": bool(loan["overdue"]),
            "renewal_count": int(loan["renewal_count"] or 0),
            "reserved": cursor.fetchone() is not None,
        }
    )
    if not can_renew:
        raise AccountError(reason)

    try:
        days = LOAN_RULES[reader_category][0]
    except (KeyError, TypeError, IndexError):
        raise AccountError("Your account does not have a borrowing period.") from None

    cursor.execute(
        """
        UPDATE loan
        SET due_at = DATE_ADD(due_at, INTERVAL %s DAY),
            renewal_count = 1
        WHERE loan_id = %s
          AND reader_id = %s
          AND returned_at IS NULL
          AND renewal_count = 0
        """,
        (days, loan_id, reader_id),
    )
    if cursor.rowcount != 1:
        raise AccountError("This loan could not be renewed.")
    return days


def load_renew_loan(loan_id, reader_id, reader_category):
    with connect() as connection, connection.cursor() as cursor:
        days = renew_loan_for_reader(cursor, loan_id, reader_id, reader_category)
        connection.commit()
        return days


@account_bp.get("/my/loans")
@role_required("reader")
def loans():
    error = None
    current_loans = []
    past_loans = []
    try:
        current_loans, past_loans = load_reader_loans(session["user_id"])
    except Exception as exc:
        error = str(exc)
    return render_template(
        "account/loans.html",
        current_loans=current_loans,
        past_loans=past_loans,
        error=error,
    )


@account_bp.get("/my/fees")
@role_required("reader")
def fees():
    error = None
    fee_rows = []
    try:
        fee_rows = load_reader_fees(session["user_id"])
    except Exception as exc:
        error = str(exc)
    return render_template("account/fees.html", fee_rows=fee_rows, error=error)


@account_bp.get("/my/notices")
@login_required
def notices():
    return render_template(
        "placeholder.html",
        heading="Notices",
        module="User & Account Management",
        detail="Optional collection notices go here.",
    )


@account_bp.post("/loans/<int:loan_id>/renew")
@role_required("reader")
def renew_loan(loan_id):
    try:
        days = load_renew_loan(
            loan_id,
            session["user_id"],
            session.get("reader_category"),
        )
    except LookupError:
        abort(403)
    except AccountError as exc:
        flash(str(exc))
        return redirect(url_for("account.loans"))
    except Exception as exc:
        flash(str(exc))
        return redirect(url_for("account.loans"))
    flash(f"Loan renewed. The due date was extended by {days} days.")
    return redirect(url_for("account.loans"))


@account_bp.post("/fees/<int:fee_id>/pay")
@role_required("librarian")
def pay_fee(fee_id):
    flash("Recording a fee payment is not implemented yet.")
    return redirect(url_for("desk.overdue"))


@account_bp.post("/notices/<int:notification_id>/read")
@login_required
def mark_notice_read(notification_id):
    flash("Marking a notice read is not implemented yet.")
    return redirect(url_for("account.notices"))
