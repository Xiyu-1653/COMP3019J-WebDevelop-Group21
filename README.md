# Know Book

COMP3019J Group 21 library management website.

The database lives in this repository as SQL files. After the team points `DATABASE_URL` at **one shared MySQL instance**, every member sees the same records.

## Database files

| File | Purpose |
|------|---------|
| `database/01_schema.sql` | Tables, keys, checks, indexes, triggers |
| `database/02_seed.sql` | Demo users, 8 starter titles, copies, loans, reservations, fees |
| `database/03_books.sql` | Extra 100 titles (id 9–108) and 210 copies; `cover_url` is `/static/covers/{isbn}.jpg` |
| `app/static/covers/` | Cover image files served by the Flask app |
| `scripts/init_db.py` | Creates/resets the database from those files |
| `scripts/fetch_books.py` | Regenerates `03_books.sql` from Open Library (optional) |

## Shared MySQL (recommended for the team)

1. Create one MySQL 8 database that all four members can reach (module server, Aiven, Railway, or similar).
2. Copy `.env.example` to `.env` and set the same URL for everyone:

   ```
   DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/knowbook
   ```

   Do not commit `.env`.
3. One member initialises the schema and sample data:

   ```
   pip install -r requirements.txt
   python scripts/init_db.py
   ```

Running `init_db.py` again drops Know Book tables and reloads the sample data.

## Demo accounts

Password for every seed account: `KnowBook123`

| Username | Role | Notes |
|----------|------|--------|
| `librarian` | librarian | Desk and inventory |
| `alice` | undergraduate | Current loan; waiting in an Algorithms queue |
| `bob` | postgraduate | Overdue loan and unpaid fee |
| `carol` | teaching staff | Current 60-day loan |
| `dave` | undergraduate | Reserved copy waiting for collection |
| `eve` | undergraduate | Current loan on Algorithms |

## Website shell

The shared Flask app lives in `app/`. It has the home page, navigation and empty routes for each management module. Module owners implement the pages on their branches; do not add a second Flask application.

```
pip install -r requirements.txt
python -m flask --app app run --debug
```

Open http://127.0.0.1:5000/

| Page | Route |
|------|--------|
| Home | `/` |
| Login | `/login` |
| Catalogue | `/catalogue` |
| Title | `/title/<id>` |
| My loans | `/my/loans` |
| My reservations | `/my/reservations` |
| Desk | `/desk` |
| Overdue | `/desk/overdue` |
| Inventory | `/inventory` |

## Connect a feature branch to main

`main` is only the website shell: routes, navigation and placeholders. Git branches cannot call each other at runtime. To see your module inside the shared site, **merge `main` into your branch**. Do not merge your branch into `main` until the module is ready.

```powershell
git checkout YOUR_BRANCH
git pull origin YOUR_BRANCH
git merge main
```

If GitHub `main` is newer than your local `main`, update `main` first:

```powershell
git checkout main
git pull origin main
git checkout YOUR_BRANCH
git merge main
```

Then run the same app as everyone else. Do not start a second Flask app.

```powershell
python -m flask --app app run --debug
```

Open http://127.0.0.1:5000/ . The home page shows **connected** next to a module when its package is present on this branch. Other modules stay as placeholders.

| Branch | Package the shell imports | Used by |
|--------|---------------------------|---------|
| `catalogue` | `catalogue/queries.py` | `/catalogue`, `/title/<id>` |
| `Borrow_Return` | `borrow_return/service.py` | `/desk` |
| `feature/reservation-inventory` | `reservation_management/` | `/my/reservations` |

### Catalogue

Keep `catalogue/queries.py` (and `common/db.py`). The shell calls `get_all_titles`, `get_title`, `get_copies_for_title` and `count_titles`. Do not run `flask --app catalogue.app`.

### Borrowing and return

Remove any standalone `borrow_return.app` Flask server. On `Borrow_Return` add:

```python
# borrow_return/__init__.py  (can be empty)
# borrow_return/service.py

def desk_context():
    """Return a dict for the desk page, e.g. copy, readers, loans."""

def borrow(reader_id, barcode):
    """Issue the copy or raise an exception."""

def return_copy(barcode):
    """Return the copy or raise an exception."""
```

`POST /desk/borrow` and `POST /desk/return` call these functions.

### Reservations

Keep `reservation_management/` with `queue`, `allocation`, `collection` and `expiration`. `/my/reservations?title_id=` uses the FIFO queue.

After a database change on `main` (for example `title.cover_url`), merge `main` into your branch and reload the sample data:

```powershell
python scripts/init_db.py
```
