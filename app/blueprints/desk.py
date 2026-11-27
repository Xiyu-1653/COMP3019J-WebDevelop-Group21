"""Borrowing & Return Management routes.

Implemented on the Borrow_Return branch as ``borrow_return/service.py``:

    desk_context() -> dict for the desk template (copy, readers, loans, error)
    borrow(reader_id, barcode, librarian_id) -> None or raises
    return_copy(barcode) -> None or raises
"""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.blueprints.auth import librarian_required, role_required
from app.integrations import load_circulation
from borrow_return.fees import generate_all_overdue_fees, load_overdue_loans

desk_bp = Blueprint("desk", __name__, template_folder="../../borrow_return/templates")


def _placeholder(heading, detail):
    return render_template(
        "placeholder.html",
        heading=heading,
        module="Borrowing & Return Management",
        detail=detail,
    )


@desk_bp.get("/desk")
@role_required("reader", "librarian")
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
    if session.get("role") == "reader":
        query = request.args.get("q", request.args.get("barcode", "")).strip()
        try:
            context = service.reader_desk_context(session["user_id"], query)
        except Exception:
            context = {"query": query, "copies": [], "loans": [],
                       "error": "Could not load the desk. Please try again."}
        return render_template("borrow_return/self_service.html", **context)
    try:
        context = service.desk_context(
            barcode=request.args.get("barcode", ""),
            reader_query=request.args.get("reader_query", ""),
            page=request.args.get("page", 1, type=int),
        )
    except Exception as exc:
        return _placeholder("Circulation desk", f"Circulation is connected, but failed: {exc}")
    return render_template("desk/index.html", **context)


@desk_bp.get("/desk/overdue")
@librarian_required
def overdue():
    error = None
    loans = []
    try:
        loans = load_overdue_loans()
    except Exception:
        error = "Could not load overdue loans. Please try again."
    return render_template("borrow_return/overdue.html", loans=loans, error=error)


@desk_bp.post("/desk/overdue/generate")
@librarian_required
def generate_fees():
    try:
        generate_all_overdue_fees()
    except Exception:
        flash("Could not generate overdue fees. Please try again.")
    else:
        flash("Overdue fees checked. Missing charges have been generated.")
    return redirect(url_for("desk.overdue"))


@desk_bp.post("/desk/borrow")
@role_required("reader", "librarian")
def borrow():
    circulation = load_circulation()
    service = circulation.get("service") if circulation else None
    if service is None:
        flash("Issuing a copy is not implemented yet.")
        return redirect(url_for("desk.index"))
    barcode = request.form.get("barcode", "").strip()
    try:
        if session["role"] == "reader":
            service.self_borrow(session["user_id"], barcode)
        else:
            service.borrow(
                request.form.get("reader_id", type=int), barcode, session["user_id"]
            )
        flash("Copy issued.")
    except Exception as exc:
        flash(str(exc))
    return redirect(url_for(
        "desk.index",
        q=request.form.get("q", "").strip(),
        barcode=barcode,
        reader_query=request.form.get("reader_query", "").strip(),
        page=request.form.get("page", 1, type=int),
    ))


@desk_bp.post("/desk/return")
@role_required("reader", "librarian")
def return_copy():
    circulation = load_circulation()
    service = circulation.get("service") if circulation else None
    if service is None:
        flash("Returning a copy is not implemented yet.")
        return redirect(url_for("desk.index"))
    barcode = request.form.get("barcode", "").strip()
    try:
        if session["role"] == "reader":
            reservation_id = service.return_copy(barcode, reader_id=session["user_id"])
        else:
            reservation_id = service.return_copy(barcode)
        if reservation_id is None:
            flash("Copy returned.")
        else:
            flash("Copy returned and held for the next reader in the reservation queue.")
    except Exception as exc:
        flash(str(exc))
    return redirect(url_for(
        "desk.index",
        q=request.form.get("q", "").strip(),
        barcode=barcode,
        reader_query=request.form.get("reader_query", "").strip(),
        page=request.form.get("page", 1, type=int),
    ))
