"""Personal loan records, renewals and account routes."""

from flask import Blueprint, abort, flash, redirect, render_template, session, url_for

from app.blueprints.auth import login_required, role_required

from borrow_return.fees import load_fee_summary, load_reader_fees
from borrow_return.renewal import AccountError, load_reader_loans, load_renew_loan

account_bp = Blueprint("account", __name__, template_folder="../../borrow_return/templates")


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
    fee_summary = None
    try:
        fee_summary = load_fee_summary(session["user_id"])
    except Exception:
        pass
    return render_template(
        "borrow_return/loans.html",
        fee_summary=fee_summary,
        current_loans=current_loans,
        past_loans=past_loans,
        error=error,
    )


@account_bp.get("/my/fees")
@role_required("reader")
def fees():
    error = None
    fees = []
    try:
        fees = load_reader_fees(session["user_id"])
    except Exception:
        error = "Could not load your fees. Please try again."
    fee_summary = None
    try:
        fee_summary = load_fee_summary(session["user_id"])
    except Exception:
        pass
    return render_template(
        "borrow_return/fees.html", fees=fees, error=error, fee_summary=fee_summary
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
    try:
        days = load_renew_loan(
            loan_id, session["user_id"], session.get("reader_category")
        )
    except LookupError:
        abort(403)
    except AccountError as exc:
        flash(str(exc))
    except Exception:
        flash("Could not renew the loan. Please try again.")
    else:
        flash(f"Loan renewed. The due date was extended by {days} days.")
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
