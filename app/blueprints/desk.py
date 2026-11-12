"""Borrowing & Return Management routes.

Implemented on the Borrow_Return branch as ``borrow_return/service.py``:

    desk_context() -> dict for the desk template (copy, readers, loans, error)
    borrow(reader_id, barcode) -> None or raises
    return_copy(barcode) -> None or raises
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.blueprints.auth import librarian_required
from app.integrations import load_circulation

desk_bp = Blueprint("desk", __name__)


def _placeholder(heading, detail):
    return render_template(
        "placeholder.html",
        heading=heading,
        module="Borrowing & Return Management",
        detail=detail,
    )


@desk_bp.get("/desk")
@librarian_required
def index():
    circulation = load_circulation()
    if circulation is None:
        return _placeholder(
            "Circulation desk",
            "Issue, return, due-today and awaiting-collection lists go here. "
            "This page fills in when Borrow_Return provides borrow_return/service.py.",
        )
    service = circulation.get("service")
    if service is None:
        return _placeholder(
            "Circulation desk",
            "The borrow_return folder is present. Add borrow_return/service.py "
            "with desk_context, borrow and return_copy.",
        )
    try:
        context = service.desk_context() or {}
    except Exception as exc:
        return _placeholder("Circulation desk", f"Circulation is connected, but failed: {exc}")
    return render_template("desk/index.html", **context)


@desk_bp.get("/desk/overdue")
@librarian_required
def overdue():
    return _placeholder(
        "Overdue and fees",
        "Overdue loans and fee generation go here.",
    )


@desk_bp.post("/desk/borrow")
@librarian_required
def borrow():
    circulation = load_circulation()
    service = circulation.get("service") if circulation else None
    if service is None:
        flash("Issuing a copy is not implemented yet.")
        return redirect(url_for("desk.index"))
    try:
        service.borrow(
            request.form.get("reader_id", type=int),
            request.form.get("barcode", "").strip(),
        )
        flash("Copy issued.")
    except Exception as exc:
        flash(str(exc))
    return redirect(url_for("desk.index"))


@desk_bp.post("/desk/return")
@librarian_required
def return_copy():
    circulation = load_circulation()
    service = circulation.get("service") if circulation else None
    if service is None:
        flash("Returning a copy is not implemented yet.")
        return redirect(url_for("desk.index"))
    try:
        service.return_copy(request.form.get("barcode", "").strip())
        flash("Copy returned.")
    except Exception as exc:
        flash(str(exc))
    return redirect(url_for("desk.index"))
