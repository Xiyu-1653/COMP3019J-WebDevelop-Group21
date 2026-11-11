"""Catalogue Management: list, title detail, and inventory."""

from flask import Blueprint, flash, redirect, render_template, url_for

from app.integrations import load_catalogue

catalogue_bp = Blueprint("catalogue", __name__)


def _placeholder(heading, detail):
    return render_template(
        "placeholder.html",
        heading=heading,
        module="Catalogue Management",
        detail=detail,
    )


@catalogue_bp.get("/catalogue")
def index():
    catalogue = load_catalogue()
    if catalogue is None:
        return _placeholder(
            "Catalogue",
            "Search, filters, pagination, titles and copies go here. "
            "This page fills in when the catalogue package is in the working tree.",
        )
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            titles = catalogue["queries"].get_all_titles(cursor)
            total = catalogue["queries"].count_titles(cursor)
    except Exception as exc:
        return _placeholder("Catalogue", f"Catalogue is connected, but the database is not ready: {exc}")
    return render_template("catalogue/index.html", titles=titles, total=total)


@catalogue_bp.get("/title/<int:title_id>")
def title_detail(title_id):
    catalogue = load_catalogue()
    if catalogue is None:
        return _placeholder(
            f"Title {title_id}",
            "Book details and per-copy status go here.",
        )
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            title = catalogue["queries"].get_title(cursor, title_id)
            copies = catalogue["queries"].get_copies_for_title(cursor, title_id)
    except Exception as exc:
        return _placeholder(f"Title {title_id}", f"Catalogue is connected, but the database is not ready: {exc}")
    status = 404 if title is None else 200
    return render_template("catalogue/title.html", title=title, copies=copies), status


@catalogue_bp.get("/inventory")
def inventory():
    return _placeholder(
        "Inventory",
        "Librarian add/edit title and copy tools go here.",
    )


@catalogue_bp.post("/titles")
def create_title():
    flash("Adding a title is not implemented yet.")
    return redirect(url_for("catalogue.inventory"))


@catalogue_bp.post("/titles/<int:title_id>")
def update_title(title_id):
    flash("Editing a title is not implemented yet.")
    return redirect(url_for("catalogue.title_detail", title_id=title_id))


@catalogue_bp.post("/copies")
def create_copy():
    flash("Registering a copy is not implemented yet.")
    return redirect(url_for("catalogue.inventory"))


@catalogue_bp.post("/copies/<int:copy_id>/status")
def update_copy_status(copy_id):
    flash("Updating copy status is not implemented yet.")
    return redirect(url_for("catalogue.inventory"))
