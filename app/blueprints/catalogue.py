"""Catalogue Management: list, title detail, and inventory."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.blueprints.auth import librarian_required, login_required
from app.integrations import load_catalogue

catalogue_bp = Blueprint("catalogue", __name__)

CATALOGUE_PAGE_SIZE = 12
_SEARCH_FIELDS = ("all", "title", "author", "isbn")


def _placeholder(heading, detail):
    return render_template(
        "placeholder.html",
        heading=heading,
        module="Catalogue Management",
        detail=detail,
    )


def _filter_args(q, field, category, available_only):
    """Return the non-default query args so pagination links stay readable."""
    args = {}
    if q:
        args["q"] = q
    if field and field != "all":
        args["field"] = field
    if category:
        args["category"] = category
    if available_only:
        args["available"] = "1"
    return args


def _page_link(page, q, field, category, available_only):
    """Build a catalogue URL that preserves the current search and filters."""
    args = _filter_args(q, field, category, available_only)
    if page and page != 1:
        args["page"] = page
    return url_for("catalogue.index", **args)


@catalogue_bp.get("/catalogue")
@login_required
def index():
    catalogue = load_catalogue()
    if catalogue is None:
        return _placeholder(
            "Catalogue",
            "Search, filters, pagination, titles and copies go here. "
            "This page fills in when the catalogue package is in the working tree.",
        )

    q = request.args.get("q", "").strip()
    field = request.args.get("field", "all").strip().lower()
    if field not in _SEARCH_FIELDS:
        field = "all"
    category = request.args.get("category", "").strip()
    available_only = request.args.get("available", "").strip() in (
        "1", "true", "yes", "on",
    )

    page = request.args.get("page", 1, type=int)
    if not page or page < 1:
        page = 1

    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            categories = catalogue["queries"].get_categories(cursor)
            total = catalogue["queries"].count_titles_matching(
                cursor, q=q, field=field, category=category,
                available_only=available_only,
            )
            total_pages = (total + CATALOGUE_PAGE_SIZE - 1) // CATALOGUE_PAGE_SIZE
            if total_pages < 1:
                total_pages = 1
            page = min(page, total_pages)
            offset = (page - 1) * CATALOGUE_PAGE_SIZE
            titles = catalogue["queries"].search_titles(
                cursor, q=q, field=field, category=category,
                available_only=available_only,
                limit=CATALOGUE_PAGE_SIZE, offset=offset,
            )
    except Exception as exc:
        return _placeholder("Catalogue", f"Catalogue is connected, but the database is not ready: {exc}")

    pagination = {
        "prev_url": _page_link(page - 1, q, field, category, available_only)
        if page > 1 else None,
        "next_url": _page_link(page + 1, q, field, category, available_only)
        if page < total_pages else None,
        "pages": [
            {
                "number": p,
                "url": _page_link(p, q, field, category, available_only),
                "current": p == page,
            }
            for p in range(1, total_pages + 1)
        ],
    }

    return render_template(
        "catalogue/index.html",
        titles=titles,
        total=total,
        page=page,
        per_page=CATALOGUE_PAGE_SIZE,
        total_pages=total_pages,
        q=q,
        field=field,
        category=category,
        categories=categories,
        available_only=available_only,
        pagination=pagination,
    )


@catalogue_bp.get("/title/<int:title_id>")
@login_required
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


def _render_inventory(catalogue, error=None, copy_form=None):
    titles, categories = [], []
    load_error = None
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            titles = catalogue["queries"].get_all_titles(cursor)
            categories = catalogue["queries"].get_categories(cursor)
    except Exception as exc:
        load_error = str(exc)
    form = copy_form or {}
    return render_template(
        "catalogue/inventory.html",
        titles=titles,
        categories=categories,
        error=error or load_error,
        copy_title=form.get("title", ""),
        copy_barcode=form.get("barcode", ""),
        copy_status=form.get("status", "available"),
        copy_location=form.get("location", ""),
    )


@catalogue_bp.get("/inventory")
@librarian_required
def inventory():
    catalogue = load_catalogue()
    if catalogue is None:
        return _placeholder(
            "Inventory",
            "Librarian add/edit title and copy tools go here.",
        )
    return _render_inventory(catalogue)


@catalogue_bp.get("/titles/<int:title_id>/edit")
@librarian_required
def edit_title(title_id):
    catalogue = load_catalogue()
    if catalogue is None:
        return _placeholder("Edit title", "Title editing tools go here.")
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            title = catalogue["queries"].get_title(cursor, title_id)
            categories = catalogue["queries"].get_categories(cursor)
    except Exception as exc:
        return _placeholder("Edit title", f"Could not load the title: {exc}")
    if title is None:
        flash("That title does not exist.")
        return redirect(url_for("catalogue.inventory"))
    return render_template(
        "catalogue/title_edit.html", title=title, categories=categories
    )


@catalogue_bp.post("/titles")
@librarian_required
def create_title():
    catalogue = load_catalogue()
    if catalogue is None:
        flash("Adding a title is not implemented yet.")
        return redirect(url_for("catalogue.inventory"))
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            catalogue["queries"].create_title(
                cursor,
                isbn=request.form.get("isbn", ""),
                title=request.form.get("title", ""),
                author=request.form.get("author", ""),
                category=request.form.get("category", ""),
                description=request.form.get("description", ""),
                has_digital_version=request.form.get("has_digital_version") == "1",
                cover_url=request.form.get("cover_url", ""),
            )
            connection.commit()
    except Exception as exc:
        flash(str(exc))
        return redirect(url_for("catalogue.inventory"))
    flash("Title added.")
    return redirect(url_for("catalogue.inventory"))


@catalogue_bp.post("/titles/<int:title_id>")
@librarian_required
def update_title(title_id):
    catalogue = load_catalogue()
    if catalogue is None:
        flash("Editing a title is not implemented yet.")
        return redirect(url_for("catalogue.inventory"))
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            catalogue["queries"].update_title(
                cursor,
                title_id,
                isbn=request.form.get("isbn", ""),
                title=request.form.get("title", ""),
                author=request.form.get("author", ""),
                category=request.form.get("category", ""),
                description=request.form.get("description", ""),
                has_digital_version=request.form.get("has_digital_version") == "1",
                cover_url=request.form.get("cover_url", ""),
            )
            connection.commit()
    except Exception as exc:
        flash(str(exc))
        return redirect(url_for("catalogue.edit_title", title_id=title_id))
    flash("Title updated.")
    return redirect(url_for("catalogue.title_detail", title_id=title_id))


@catalogue_bp.post("/copies")
@librarian_required
def create_copy():
    catalogue = load_catalogue()
    if catalogue is None:
        flash("Registering a copy is not implemented yet.")
        return redirect(url_for("catalogue.inventory"))

    form = {
        "title": request.form.get("title", "").strip(),
        "barcode": request.form.get("barcode", "").strip(),
        "status": request.form.get("status", "available"),
        "location": request.form.get("location", "").strip(),
    }
    error = None
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            title_id = catalogue["queries"].find_title_id_by_name(
                cursor, form["title"]
            )
            if title_id is None:
                error = "That title does not exist."
            else:
                catalogue["queries"].create_copy(
                    cursor,
                    title_id=title_id,
                    barcode=form["barcode"],
                    status=form["status"],
                    location=form["location"],
                )
                connection.commit()
    except Exception as exc:
        error = str(exc)

    if error:
        return _render_inventory(catalogue, error=error, copy_form=form)
    flash("Copy registered.")
    return redirect(url_for("catalogue.inventory"))


@catalogue_bp.post("/copies/<int:copy_id>/status")
@librarian_required
def update_copy_status(copy_id):
    catalogue = load_catalogue()
    if catalogue is None:
        flash("Updating copy status is not implemented yet.")
        return redirect(url_for("catalogue.inventory"))
    title_id = request.form.get("title_id", type=int)
    try:
        with catalogue["connect"]() as connection, connection.cursor() as cursor:
            catalogue["queries"].update_copy_status(
                cursor,
                copy_id,
                request.form.get("status", ""),
                location=request.form.get("location", ""),
            )
            connection.commit()
    except Exception as exc:
        flash(str(exc))
    else:
        flash("Copy status updated.")
    if title_id:
        return redirect(url_for("catalogue.title_detail", title_id=title_id))
    return redirect(url_for("catalogue.inventory"))
