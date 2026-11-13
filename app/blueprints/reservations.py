"""Reservation & Inventory Management: queue and collection."""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

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

    if not session.get("user_id"):
        flash("Please log in to see your reservations.")
        return redirect(url_for("auth.login"))
    if session.get("role") != "reader":
        flash("Reservations belong to reader accounts.")
        return redirect(url_for("reservations.queue_admin"))

    reservation_rows = []
    error = None
    try:
        with reservations["connect"]() as connection, connection.cursor() as cursor:
            reservations["expiration"].process_expired_reservations(cursor)
            reservation_rows = reservations["queue"].get_reader_reservations(
                cursor, session["user_id"]
            )
            connection.commit()
    except Exception as exc:
        error = str(exc)

    return render_template(
        "reservations/index.html",
        reservation_rows=reservation_rows,
        error=error,
    )


@reservations_bp.get("/desk/reservations")
def queue_admin():
    if not session.get("user_id"):
        flash("Please log in as a librarian to manage reservation queues.")
        return redirect(url_for("auth.login"))
    if session.get("role") != "librarian":
        abort(403)

    reservations = load_reservations()
    if reservations is None:
        return render_template(
            "placeholder.html",
            heading="Reservation queues",
            module="Reservation & Inventory Management",
            detail="Search a book title to see its waiting queue. "
            "This page fills in when reservation_management is in the working tree.",
        )

    keyword = request.args.get("q", "").strip()
    title_results = []
    error = None
    if keyword:
        try:
            with reservations["connect"]() as connection, connection.cursor() as cursor:
                reservations["expiration"].process_expired_reservations(cursor)
                title_results = reservations["queue"].find_waiting_queues(
                    cursor, keyword
                )
                connection.commit()
        except Exception as exc:
            error = str(exc)

    return render_template(
        "reservations/queues.html",
        keyword=keyword,
        title_results=title_results,
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
