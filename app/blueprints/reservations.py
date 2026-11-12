"""Reservation & Inventory Management: queue and collection."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.blueprints.auth import librarian_required, login_required
from app.integrations import load_reservations

reservations_bp = Blueprint("reservations", __name__)


@reservations_bp.get("/my/reservations")
@login_required
def my_reservations():
    reservations = load_reservations()
    if reservations is None:
        return render_template(
            "placeholder.html",
            heading="My reservations",
            module="Reservation & Inventory Management",
            detail="Queue position, cancellation and collection deadline go here. "
            "This page fills in when reservation_management is in the working tree.",
        )

    title_id = request.args.get("title_id", type=int)
    queue_rows = []
    error = None
    if title_id is not None:
        try:
            with reservations["connect"]() as connection, connection.cursor() as cursor:
                reservations["expiration"].process_expired_reservations(cursor)
                connection.commit()
                queue_rows = reservations["queue"].get_waiting_queue(cursor, title_id)
        except Exception as exc:
            error = str(exc)

    return render_template(
        "reservations/index.html",
        title_id=title_id,
        queue_rows=queue_rows,
        error=error,
    )


@reservations_bp.post("/title/<int:title_id>/reserve")
@login_required
def place_hold(title_id):
    flash("Placing a reservation is not implemented yet.")
    return redirect(url_for("catalogue.title_detail", title_id=title_id))


@reservations_bp.post("/reservations/<int:reservation_id>/cancel")
@login_required
def cancel(reservation_id):
    flash("Cancelling a reservation is not implemented yet.")
    return redirect(url_for("reservations.my_reservations"))


@reservations_bp.post("/desk/collect")
@librarian_required
def collect():
    reservations = load_reservations()
    if reservations is None:
        flash("Collecting a reserved copy is not implemented yet.")
        return redirect(url_for("desk.index"))

    reservation_id = request.form.get("reservation_id", type=int)
    librarian_id = request.form.get("librarian_id", type=int)
    loan_days = request.form.get("loan_days", type=int)
    if not reservation_id or not librarian_id or not loan_days:
        flash("Collection needs reservation_id, librarian_id and loan_days.")
        return redirect(url_for("desk.index"))
    try:
        with reservations["connect"]() as connection, connection.cursor() as cursor:
            reservations["collection"].collect_reservation(
                cursor, reservation_id, librarian_id, loan_days
            )
            connection.commit()
    except Exception as exc:
        flash(str(exc))
        return redirect(url_for("desk.index"))
    flash("Reserved copy collected.")
    return redirect(url_for("desk.index"))
