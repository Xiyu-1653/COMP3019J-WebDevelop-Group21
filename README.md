# Know Book

COMP3019J Group 21 library management website.

The database lives in this repository as SQL files. After the team points `DATABASE_URL` at **one shared MySQL instance**, every member sees the same records.

## Database files

| File | Purpose |
|------|---------|
| `database/01_schema.sql` | Tables, keys, checks, indexes, triggers |
| `database/02_seed.sql` | Demo users, titles, copies, loans, reservations, fees |
| `scripts/init_db.py` | Creates/resets the database from those files |

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

The older circulation demo in `borrow_return/` is still available. See [borrow_return/README.md](borrow_return/README.md).
