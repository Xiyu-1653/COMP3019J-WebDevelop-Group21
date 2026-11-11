"""Reservation & Inventory Management: queue and collection placeholders."""

from flask import Blueprint, flash, redirect, render_template, url_for

reservations_bp = Blueprint("reservations", __name__)


@reservations_bp.get("/my/reservations")
def my_reservations():
    return render_template(
        "placeholder.html",
        heading="My reservations",
        module="Reservation & Inventory Management",
        detail="Queue position, cancellation and collection deadline go here.",
    )


@reservations_bp.post("/title/<int:title_id>/reserve")
def place_hold(title_id):
    flash("Placing a reservation is not implemented yet.")
    return redirect(url_for("catalogue.title_detail", title_id=title_id))


@reservations_bp.post("/reservations/<int:reservation_id>/cancel")
def cancel(reservation_id):
    flash("Cancelling a reservation is not implemented yet.")
    return redirect(url_for("reservations.my_reservations"))


@reservations_bp.post("/desk/collect")
def collect():
    flash("Collecting a reserved copy is not implemented yet.")
    return redirect(url_for("desk.index"))
