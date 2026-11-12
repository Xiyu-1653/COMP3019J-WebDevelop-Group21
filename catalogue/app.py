"""Catalogue backend: browse titles and view physical copies.

Stage 1 provides the read-only backend foundation. Pagination, search and
filtering are added in later stages. Run from the repo root:

    python -m flask --app catalogue.app run --port 5082
"""

from flask import Flask, render_template

from catalogue import queries
from common.db import connect

app = Flask(__name__)


@app.get("/")
def catalogue_index():
    with connect() as connection, connection.cursor() as cursor:
        titles = queries.get_all_titles(cursor)
        total = queries.count_titles(cursor)
    return render_template("catalogue.html", titles=titles, total=total)


@app.get("/title/<int:title_id>")
def title_detail(title_id):
    with connect() as connection, connection.cursor() as cursor:
        title = queries.get_title(cursor, title_id)
        copies = queries.get_copies_for_title(cursor, title_id)
    if title is None:
        return render_template("title.html", title=None, copies=[]), 404
    return render_template("title.html", title=title, copies=copies)
