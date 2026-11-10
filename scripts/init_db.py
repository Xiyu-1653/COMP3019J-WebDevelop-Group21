"""Create or reset the Know Book MySQL database from files in database/.

Usage:
    python scripts/init_db.py

Reads DATABASE_URL from .env, for example:
    mysql+pymysql://USER:PASSWORD@HOST:3306/knowbook
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from pymysql.constants import CLIENT

ROOT = Path(__file__).resolve().parents[1]
DATABASE_DIR = ROOT / "database"
ENV_FILE = ROOT / ".env"


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_database_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise SystemExit("DATABASE_URL must be a mysql:// or mysql+pymysql:// URL")
    if not parsed.hostname or not parsed.username:
        raise SystemExit("DATABASE_URL must include username and host")
    database = (parsed.path or "/knowbook").lstrip("/") or "knowbook"
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username),
        "password": unquote(parsed.password or ""),
        "database": database,
    }


def split_sql(sql: str) -> list[str]:
    """Split a MySQL script into statements, honouring DELIMITER changes."""
    statements: list[str] = []
    delimiter = ";"
    buffer: list[str] = []

    for raw_line in sql.splitlines():
        line = raw_line
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("#"):
            continue
        delimiter_match = re.match(r"^DELIMITER\s+(\S+)\s*$", stripped, re.IGNORECASE)
        if delimiter_match:
            current = "".join(buffer).strip()
            if current:
                statements.append(current)
            buffer = []
            delimiter = delimiter_match.group(1)
            continue
        buffer.append(line + "\n")
        current = "".join(buffer)
        if current.rstrip().endswith(delimiter):
            statement = current.rstrip()[: -len(delimiter)].strip()
            if statement:
                statements.append(statement)
            buffer = []

    leftover = "".join(buffer).strip()
    if leftover:
        statements.append(leftover)
    return statements


def run_sql_file(cursor, path: Path) -> None:
    print(f"Applying {path.name} ...")
    for statement in split_sql(path.read_text(encoding="utf-8")):
        cursor.execute(statement)


def main() -> None:
    load_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit(
            "Set DATABASE_URL in .env (copy .env.example). "
            "Use one shared MySQL URL so every teammate sees the same data."
        )

    cfg = parse_database_url(url)
    admin = {k: v for k, v in cfg.items() if k != "database"}
    conn = pymysql.connect(**admin, charset="utf8mb4", client_flag=CLIENT.MULTI_STATEMENTS)
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            except pymysql.err.OperationalError:
                # Some shared hosts already provide a database and forbid CREATE DATABASE.
                pass
            cursor.execute(f"USE `{cfg['database']}`")
            run_sql_file(cursor, DATABASE_DIR / "01_schema.sql")
            run_sql_file(cursor, DATABASE_DIR / "02_seed.sql")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("Know Book database is ready.")
    print("Demo login: librarian / alice / bob / carol / dave / eve")
    print("Demo password for every seed account: KnowBook123")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Database init failed: {exc}", file=sys.stderr)
        sys.exit(1)
