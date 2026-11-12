"""Optional hooks into feature-branch packages.

The website on main only contains Flask routes. It looks for packages in the
current working tree. If a package is missing, that page stays a placeholder.

Merge main into a feature branch (not the other way around) so that branch
has the shell plus its package. You do not have to merge the feature back
into main to try it.
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
    """Borrow_Return branch should provide borrow_return/service.py."""
    if not (ROOT / "borrow_return").is_dir():
        return None
    try:
        from borrow_return import service
    except ImportError:
        return {"service": None}
    return {"service": service}


def loaded_modules():
    circulation = load_circulation()
    return {
        "catalogue": load_catalogue() is not None,
        "reservations": load_reservations() is not None,
        "circulation": circulation is not None and circulation.get("service") is not None,
    }
