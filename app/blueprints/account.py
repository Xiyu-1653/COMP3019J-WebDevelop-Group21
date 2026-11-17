"""User & Account Management: personal loan records."""

from flask import Blueprint, flash, redirect, render_template, session, url_for

from app.blueprints.auth import login_required, role_required
from common.db import connect

account_bp = Blueprint("account", __name__)

LOAN_QUERY = """
    SELECT
        l.loan_id,
        l.borrowed_at,
        l.due_at,
        l.returned_at,
        l.renewal_count,
        (l.returned_at IS NULL AND l.due_at < NOW()) AS overdue,
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


def get_reader_loans(cursor, reader_id):
    """Return ``(current, history)`` loan rows for one reader only."""
    cursor.execute(LOAN_QUERY, (reader_id,))
    current = []
    history = []
    for row in cursor.fetchall() or ():
        item = dict(row)
        item["overdue"] = bool(item.get("overdue"))
        if item["returned_at"] is None:
            current.append(item)
        else:
            history.append(item)
    return current, history


def load_reader_loans(reader_id):
    with connect() as connection, connection.cursor() as cursor:
        return get_reader_loans(cursor, reader_id)


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
@login_required
def fees():
    return render_template(
        "placeholder.html",
        heading="Fee history",
        module="User & Account Management",
        detail="Optional reader fee history goes here.",
    )


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
    flash("Renewal is not implemented yet.")
    return redirect(url_for("account.loans"))


@account_bp.post("/fees/<int:fee_id>/pay")
@login_required
def pay_fee(fee_id):
    flash("Recording a fee payment is not implemented yet.")
    return redirect(url_for("desk.overdue"))


@account_bp.post("/notices/<int:notification_id>/read")
@login_required
def mark_notice_read(notification_id):
    flash("Marking a notice read is not implemented yet.")
    return redirect(url_for("account.notices"))
