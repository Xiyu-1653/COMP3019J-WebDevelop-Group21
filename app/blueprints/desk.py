"""Borrowing & Return Management: circulation desk placeholders."""

from flask import Blueprint, flash, redirect, render_template, url_for

desk_bp = Blueprint("desk", __name__)


@desk_bp.get("/desk")
def index():
    return render_template(
        "placeholder.html",
        heading="Circulation desk",
        module="Borrowing & Return Management",
        detail="Issue, return, due-today and awaiting-collection lists go here.",
    )


@desk_bp.get("/desk/overdue")
def overdue():
    return render_template(
        "placeholder.html",
        heading="Overdue and fees",
        module="Borrowing & Return Management",
        detail="Overdue loans and fee generation go here.",
    )


@desk_bp.post("/desk/borrow")
def borrow():
    flash("Issuing a copy is not implemented yet.")
    return redirect(url_for("desk.index"))


@desk_bp.post("/desk/return")
def return_copy():
    flash("Returning a copy is not implemented yet.")
    return redirect(url_for("desk.index"))
