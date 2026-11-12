"""Shared MySQL connection helper for Know Book.

Every module (Catalogue, Borrowing, Reservation, Inventory) opens its
connection through this one helper so they all read and write the same
MySQL instance. Configure it with ``DATABASE_URL`` (preferred) or the
``DB_*`` environment variables.
"""

from __future__ import annotations

import os

import pymysql
from pymysql.cursors import DictCursor

from scripts.init_db import load_env, parse_database_url

load_env()


def connect():
    """Return a new connection to the shared Know Book MySQL database.

    Uses the same configuration as ``scripts/init_db.py`` so the application
    and the database initialisation script always point at one database.
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        return pymysql.connect(
            **parse_database_url(database_url),
            charset="utf8mb4",
            cursorclass=DictCursor,
        )
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "knowbook"),
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "knowbook"),
        charset="utf8mb4",
        cursorclass=DictCursor,
    )
