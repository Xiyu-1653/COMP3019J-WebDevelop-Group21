"""Optional hooks into feature-branch packages.

Git branches cannot run inside each other. The website looks for well-known
folders in the current working tree. If a folder is missing, that page stays
a placeholder. Merge main into a feature branch so that branch has both the
shell and its package; you do not have to merge the feature back into main
to try it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_catalogue():
    if not (ROOT / "catalogue" / "queries.py").is_file():
        return None
    try:
        from catalogue import queries
        from common.db import connect
    except ImportError:
        return None
    return {"queries": queries, "connect": connect}


def load_reservations():
    if not (ROOT / "reservation_management" / "queue.py").is_file():
        return None
    try:
        from common.db import connect
        from reservation_management import allocation, collection, expiration, queue
    except ImportError:
        return None
    return {
        "connect": connect,
        "queue": queue,
        "allocation": allocation,
        "collection": collection,
        "expiration": expiration,
    }


def load_circulation():
    return (ROOT / "borrow_return" / "app.py").is_file()


def loaded_modules():
    return {
        "catalogue": load_catalogue() is not None,
        "reservations": load_reservations() is not None,
        "circulation": load_circulation(),
    }
