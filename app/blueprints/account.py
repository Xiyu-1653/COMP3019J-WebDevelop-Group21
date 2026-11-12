"""User & Account Management: personal records placeholders."""

from flask import Blueprint, flash, redirect, render_template, url_for

from app.blueprints.auth import login_required

account_bp = Blueprint("account", __name__)


@account_bp.get("/my/loans")
@login_required
def loans():
    return render_template(
        "placeholder.html",
        heading="My loans",
        module="User & Account Management",
        detail="Current and past loans go here. Renewal is posted below.",
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
@login_required
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
