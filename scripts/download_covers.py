"""Download covers into app/static/covers and rewrite SQL to site links."""

from __future__ import annotations

import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVER_DIR = ROOT / "app" / "static" / "covers"
SQL_FILES = [ROOT / "database" / "02_seed.sql", ROOT / "database" / "03_books.sql"]
UA = {"User-Agent": "KnowBook-catalogue/1.0 (COMP3019J group project)"}
URL_RE = re.compile(
    r"https://covers\.openlibrary\.org/b/isbn/(\d{10,13})-L\.jpg"
)
LOCAL_RE = re.compile(r"/static/covers/(\d{10,13})\.jpg")


def collect_isbns() -> list[str]:
    found: list[str] = []
    for path in SQL_FILES:
        text = path.read_text(encoding="utf-8")
        found.extend(URL_RE.findall(text))
        found.extend(LOCAL_RE.findall(text))
    return list(dict.fromkeys(found))


def download(isbn: str) -> str:
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    dest = COVER_DIR / f"{isbn}.jpg"
    if dest.exists() and dest.stat().st_size > 500:
        return f"HAVE {isbn}"
    urls = [
        f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg",
        f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg",
    ]
    for url in urls:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                data = resp.read()
                ctype = (resp.headers.get("Content-Type") or "").lower()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = str(exc)
            continue
        if "image" in ctype and len(data) >= 500:
            dest.write_bytes(data)
            return f"OK {isbn} ({len(data)} bytes)"
        last = f"not an image ({len(data)} bytes)"
    return f"FAIL {isbn}: {last}"


def rewrite_sql() -> None:
    for path in SQL_FILES:
        text = path.read_text(encoding="utf-8")
        updated = URL_RE.sub(r"/static/covers/\1.jpg", text)
        path.write_text(updated, encoding="utf-8")
        print(f"rewrote {path.name}", flush=True)


def main() -> None:
    isbns = collect_isbns()
    print(f"Downloading {len(isbns)} covers ...", flush=True)
    ok = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(download, isbn): isbn for isbn in isbns}
        for future in as_completed(futures):
            line = future.result()
            print(line, flush=True)
            if line.startswith("OK") or line.startswith("HAVE"):
                ok += 1
    rewrite_sql()
    print(f"Saved {ok}/{len(isbns)} covers to {COVER_DIR}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
