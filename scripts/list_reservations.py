"""Print every reservation record.

Usage:
    python scripts/list_reservations.py
    python scripts/list_reservations.py --status waiting
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.db import connect  # noqa: E402

STATUSES = ("waiting", "ready", "fulfilled", "cancelled", "expired")

QUERY = """
    SELECT r.reservation_id, r.status, r.reader_id, u.username,
           r.title_id, t.title, r.reserved_at, r.collect_deadline,
           r.allocated_copy_id, c.barcode AS copy_barcode
    FROM reservation AS r
    JOIN user AS u ON u.user_id = r.reader_id
    JOIN title AS t ON t.title_id = r.title_id
    LEFT JOIN copy AS c ON c.copy_id = r.allocated_copy_id
    {where}
    ORDER BY r.reservation_id
"""


def main():
    parser = argparse.ArgumentParser(description="List reservation records.")
    parser.add_argument("--status", choices=STATUSES, help="Only show one status.")
    args = parser.parse_args()

    where = ""
    params = []
    if args.status:
        where = "WHERE r.status = %s"
        params.append(args.status)

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(QUERY.format(where=where), params)
        rows = cursor.fetchall()

    print(
        f"{'ID':>3}  {'Status':<10} {'Reader':<10} {'Title':<36} "
        f"{'Reserved at':<20} {'Deadline':<20} {'Copy':<8}"
    )
    print("-" * 118)
    for row in rows:
        print(
            f"{row['reservation_id']:>3}  {row['status']:<10} "
            f"{row['username']:<10} {str(row['title'])[:36]:<36} "
            f"{str(row['reserved_at']):<20} "
            f"{str(row['collect_deadline'] or '-'):<20} "
            f"{row['copy_barcode'] or '-':<8}"
        )
    print(f"\n{len(rows)} record(s).")


if __name__ == "__main__":
    main()
