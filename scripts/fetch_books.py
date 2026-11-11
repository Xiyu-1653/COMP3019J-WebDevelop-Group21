"""Fetch 100 real books (ISBN + cover) and emit database/03_books.sql.

Data sources
------------
- Open Library search: title / author / ISBN / subjects / work key.
- Open Library covers API: cover URL keyed to the exact ISBN (so a cover is
  never mixed with another edition of the same title).
- Google Books: optional supplement for description / ebook flag, used only
  when the keyless endpoint is not rate-limited.

The ISBN-13 is canonicalised (ISBN-10 is converted) and deduplicated, and a
book is kept only when a cover exists for that exact ISBN.

Output format matches database/02_seed.sql. title_id continues at 9 and
copy_id continues at 18, so the file can be applied on top of the seed:

    python scripts/fetch_books.py            # writes database/03_books.sql
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "database" / "03_books.sql"
UA = {"User-Agent": "KnowBook-catalogue/1.0 (COMP3019J group project)"}

# (search query, category) pairs. Keyword search surfaces well-known works.
QUERIES = [
    ("computer programming", "Computing"),
    ("software engineering", "Computing"),
    ("artificial intelligence", "Computing"),
    ("data structures algorithms", "Computing"),
    ("fiction", "Fiction"),
    ("science fiction", "Fiction"),
    ("fantasy", "Fiction"),
    ("classic literature", "Literature"),
    ("poetry", "Literature"),
    ("physics", "Science"),
    ("biology", "Science"),
    ("chemistry", "Science"),
    ("astronomy", "Science"),
    ("world history", "History"),
    ("philosophy", "Philosophy"),
    ("mathematics", "Mathematics"),
    ("economics", "Business"),
    ("business management", "Business"),
    ("psychology", "Psychology"),
    ("art history", "Art"),
    ("biography", "Biography"),
]

TARGET = 100
MAX_PER_QUERY = 5
GOOGLE_OK = False


def probe_google():
    global GOOGLE_OK
    try:
        url = (
            "https://www.googleapis.com/books/v1/volumes?"
            + urllib.parse.urlencode({"q": "isbn:9780132350884"})
        )
        fetch_json(url, retries=1)
        GOOGLE_OK = True
    except Exception:
        GOOGLE_OK = False
    print(f"Google Books supplement enabled: {GOOGLE_OK}")


def http_get(url, timeout=20, retries=4):
    """Return response body bytes, with retries and exponential backoff."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - network is inherently fickle
            last = exc
            time.sleep(1.5 ** attempt)
    raise last


def fetch_json(url, timeout=20, retries=4):
    return json.loads(http_get(url, timeout=timeout, retries=retries).decode("utf-8"))


def has_cover(isbn13):
    url = f"https://covers.openlibrary.org/b/isbn/{isbn13}-L.jpg?default=false"
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as exc:
            return exc.code != 404
        except Exception:  # noqa: BLE001
            time.sleep(1.5 ** attempt)
    return False


def isbn13_check(twelve: str) -> str:
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(twelve))
    return str((10 - (total % 10)) % 10)


def to_isbn13(raw: str) -> str | None:
    s = re.sub(r"[^0-9Xx]", "", raw).upper()
    if len(s) == 10:
        if not s[:9].isdigit() or not (s[9].isdigit() or s[9] == "X"):
            return None
        total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(s))
        if total % 11 != 0:
            return None
        body = "978" + s[:9]
        return body + isbn13_check(body)
    if len(s) == 13 and s.isdigit() and s[:3] in ("978", "979"):
        if isbn13_check(s[:12]) != s[12]:
            return None
        return s
    return None


def candidate_isbn13s(isbns):
    seen, out = set(), []
    for raw in isbns:
        i13 = to_isbn13(raw)
        if i13 and i13 not in seen:
            seen.add(i13)
            out.append(i13)
    return out


def norm_title(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def clean_text(value, limit=600):
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return None
    return text[:limit].strip()


def works_description(work_key):
    if not work_key.startswith("/works/"):
        return None
    try:
        data = fetch_json(f"https://openlibrary.org{work_key}.json", retries=2)
    except Exception:
        return None
    desc = data.get("description")
    if isinstance(desc, str):
        return clean_text(desc)
    if isinstance(desc, dict) and isinstance(desc.get("value"), str):
        return clean_text(desc["value"])
    return None


def sql_escape(value):
    if value is None:
        return "NULL"
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def collect_books():
    books, seen_titles = [], set()
    for query, category in QUERIES:
        if len(books) >= TARGET:
            break
        url = (
            "https://openlibrary.org/search.json?"
            + urllib.parse.urlencode(
                {"q": query, "limit": 40,
                 "fields": "key,title,author_name,isbn,subject"}
            )
        )
        try:
            payload = fetch_json(url)
        except Exception as exc:
            print(f"  ! search failed ({query}): {exc}")
            continue
        collected_here = 0
        for doc in payload.get("docs", []):
            if len(books) >= TARGET or collected_here >= MAX_PER_QUERY:
                break
            title = doc.get("title")
            authors = doc.get("author_name") or []
            if not title or not authors:
                continue
            ntitle = norm_title(title)
            if ntitle in seen_titles:
                continue
            isbn13s = candidate_isbn13s(doc.get("isbn") or [])
            if not isbn13s:
                continue
            picked = None
            for i13 in isbn13s:
                if has_cover(i13):
                    picked = i13
                    break
            if not picked:
                continue
            seen_titles.add(ntitle)
            books.append(
                {
                    "isbn": picked,
                    "title": title,
                    "author": authors[0],
                    "category": category,
                    "key": doc.get("key", ""),
                }
            )
            collected_here += 1
            print(f"  [{len(books):3d}] {title[:45]:45s}  {picked}  {category}")
        time.sleep(0.2)
    return books


def google_supplement(isbn):
    """Best-effort description + ebook flag from Google Books. Returns (desc, is_ebook)."""
    if not GOOGLE_OK:
        return None, False
    url = (
        "https://www.googleapis.com/books/v1/volumes?"
        + urllib.parse.urlencode({"q": f"isbn:{isbn}"})
    )
    try:
        payload = fetch_json(url, retries=2)
    except Exception:
        return None, False
    items = payload.get("items") or []
    if not items:
        return None, False
    info = items[0].get("volumeInfo", {})
    desc = clean_text(info.get("description"))
    is_ebook = bool((items[0].get("saleInfo") or {}).get("isEbook"))
    return desc, is_ebook


def build_sql(books):
    lines = [
        "-- Know Book extra catalogue data (100 books).",
        "-- Generated by scripts/fetch_books.py from Open Library search + covers",
        "-- (ISBN-keyed) with Google Books as an optional supplement.",
        "-- Every title has a unique ISBN and a cover URL keyed to that exact ISBN,",
        "-- so different editions are never mixed by title alone.",
        "-- title_id continues at 9 (02_seed.sql uses 1-8); copy_id continues at 18.",
        "",
        "SET NAMES utf8mb4;",
        "",
        "INSERT INTO title (title_id, isbn, title, author, category, description, has_digital_version, cover_url, created_at) VALUES",
    ]

    title_rows = []
    copy_rows = []
    copy_seq = 18
    base = dt.datetime(2026, 8, 1, 9, 0, 0)
    extra_status_cycle = [
        "available", "available", "available", "borrowed", "reserved",
        "available", "damaged", "available", "lost", "available",
        "under_repair", "available",
    ]
    location_for_status = {
        "available": None,
        "borrowed": "On loan",
        "reserved": "Hold shelf",
        "damaged": "Repair room",
        "lost": "Missing",
        "under_repair": "Repair room",
    }

    for i, book in enumerate(books):
        title_id = 9 + i
        created = base + dt.timedelta(hours=22 * i)
        cover = f"https://covers.openlibrary.org/b/isbn/{book['isbn']}-L.jpg"

        desc = works_description(book["key"])
        is_ebook = False
        gdesc, g_ebook = google_supplement(book["isbn"])
        if gdesc:
            desc = gdesc
        is_ebook = g_ebook
        has_digital = 1 if is_ebook else 0

        title_rows.append(
            f"    ({title_id}, {sql_escape(book['isbn'])}, {sql_escape(book['title'])}, "
            f"{sql_escape(book['author'])}, {sql_escape(book['category'])},\n"
            f"        {sql_escape(desc)}, {has_digital},\n"
            f"        {sql_escape(cover)}, {sql_escape(created.strftime('%Y-%m-%d %H:%M:%S'))})"
        )

        n_copies = 3 if i % 10 == 0 else 2
        for j in range(n_copies):
            if j == 0:
                status = "available"
            else:
                status = extra_status_cycle[(i + j) % len(extra_status_cycle)]
            if status == "available":
                location = f"{chr(65 + (i % 6))}-{(i % 20):02d}-{1 + (i % 5):02d}"
            else:
                location = location_for_status[status]
            barcode = f"KB-{copy_seq:04d}"
            copy_rows.append(
                f"    ({copy_seq}, {title_id}, {sql_escape(barcode)}, "
                f"{sql_escape(status)}, {sql_escape(location)})"
            )
            copy_seq += 1

    lines.append(",\n".join(title_rows) + ";")
    lines.append("")
    lines.append(
        "INSERT INTO copy (copy_id, title_id, barcode, status, location) VALUES"
    )
    lines.append(",\n".join(copy_rows) + ";")
    lines.append("")
    return "\n".join(lines)


def main():
    probe_google()
    print(f"Collecting {TARGET} books from Open Library (Google Books as supplement)...")
    books = collect_books()
    if len(books) < TARGET:
        print(f"WARNING: only collected {len(books)} books (target {TARGET}).")
    sql = build_sql(books)
    OUT.write_text(sql, encoding="utf-8")
    print(f"\nWrote {OUT} with {len(books)} titles.")
    cats = {}
    for b in books:
        cats[b["category"]] = cats.get(b["category"], 0) + 1
    print("Categories:", json.dumps(cats))


if __name__ == "__main__":
    main()
