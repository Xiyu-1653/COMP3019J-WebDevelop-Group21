"""Catalogue Management: list, title detail, and inventory placeholders."""

from flask import Blueprint, flash, redirect, render_template, url_for

catalogue_bp = Blueprint("catalogue", __name__)


@catalogue_bp.get("/catalogue")
def index():
    return render_template(
        "placeholder.html",
        heading="Catalogue",
        module="Catalogue Management",
        detail="Search, filters, pagination, titles and copies go here.",
    )


@catalogue_bp.get("/title/<int:title_id>")
def title_detail(title_id):
    return render_template(
        "placeholder.html",
        heading=f"Title {title_id}",
        module="Catalogue Management",
        detail="Book details and per-copy status go here.",
    )


@catalogue_bp.get("/inventory")
def inventory():
    return render_template(
        "placeholder.html",
        heading="Inventory",
        module="Catalogue Management",
        detail="Librarian add/edit title and copy tools go here.",
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
