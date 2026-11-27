# Borrowing and returns

This package provides the services used by the shared Flask desk routes. Run commands from the repository root.

## Run locally

Install the dependencies in the existing Python environment.

```powershell
python -m pip install -r requirements.txt
```

Configure DATABASE_URL in the root .env file, following .env.example. All modules use common/db.py and the same database connection. The existing DB_HOST, DB_PORT, DB_USER, DB_PASSWORD and DB_NAME environment variables are also supported. DATABASE_URL takes priority.

For the previously prepared local demo database, set the following in PowerShell. Enter the local MySQL credentials in the prompt.

```powershell
$credential = Get-Credential -UserName root -Message "Enter local MySQL credentials"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DB_USER = $credential.UserName
$env:DB_PASSWORD = $credential.GetNetworkCredential().Password
$env:DB_NAME = "knowbook_c_demo"
python -m flask --app app run --debug
```

Open http://127.0.0.1:5000/ and select Circulation desk. The home page shows connected for borrowing and returns. The desk is available at /desk.

Use the existing project schema and seed data. Running scripts/init_db.py resets the configured database, so use it only when a reset is intended.

## Service interface

- desk_context(barcode) returns the copy, readers and loans used by the desk template.
- borrow(reader_id, barcode, librarian_id) validates borrowing eligibility and commits the loan and copy changes together.
- return_copy(barcode) closes the loan, assigns the item to the first waiting reservation if present, and commits all changes together. It returns the reservation ID, or None when no reader is waiting.

The shared routes in app/blueprints/desk.py call these functions. The desk page uses app/templates/desk/index.html and extends the shared base template.

## Demonstration

Enter an item barcode, such as KB-0001, to show its details and loan history. The desk passes the logged-in librarian's user ID from the server session to the service. Each new loan records that librarian ID.

1. Choose alice and check out the item. Confirm its status becomes Borrowed and a loan with a 14-day period appears.
2. Refresh the page and confirm that the record remains.
3. Return the item. Confirm its status becomes Available and its return time appears.
4. Choose bob and attempt checkout. Confirm an overdue-loan message appears and no new loan is added.

Alice's original seed loan is due on 15 November 2026. After it becomes overdue, use carol before her seed loan becomes overdue on 19 December 2026, or first resolve Alice's overdue loan. Carol receives a 60-day borrowing period.

The services check copy availability, overdue loans, unpaid fees and distinct-title borrowing limits. Returned items are assigned to the first waiting reader using reservation_management.allocation. The item becomes reserved, the reservation becomes ready, and a collection notification is created. The collection deadline uses collection_window_days from system_config. Items with no waiting reader remain available. Overdue fee generation is described below.

## Reader renewals

Readers open My loans to see their current and past loans. Renewal services and queries are in borrow_return/renewal.py, adapted from the login branch's account implementation. The page template is borrow_return/templates/borrow_return/loans.html.

A reader can renew their own open loan once, strictly before the due time, when no reservation is waiting for that title. The server checks these conditions again on submission. It extends the existing due date by the reader category's normal borrowing period: 14, 30 or 60 days. The loan's renewal_count becomes 1.

The copy and loan are locked during renewal to serialize competing return and renewal operations. The conditional update also rejects already renewed, returned or expired loans.

## Overdue fees

Each overdue loan receives a single fixed charge from system_config.overdue_fee_amount (5.00 in the seed data). The charge is not a daily rate. An open loan is overdue when due_at is earlier than the current database time. A returned loan qualifies when returned_at is later than due_at.

Returning an item generates any missing overdue charges for that copy in the same transaction as the return and reservation allocation. Librarians can also open Overdue and select Generate overdue fees to process all missing charges, including unreturned overdue loans. There is no scheduled background task.

The database's unique (loan_id, reason) key prevents duplicate overdue fees. Existing amounts and paid/cancelled statuses are preserved. No schema change is needed for the project's current schema.

Readers see their own records through My loans > Fee history. Fees are generated on late return or the librarian's generation action. Recording payment remains a separate, unfinished feature.

## Desk reader search and history pages

After finding an item, search for a reader using a username prefix or an exact user ID. The page shows at most 20 matches and asks for a more specific search when additional matches exist. Empty searches do not load the reader list. Select the correct reader before checkout.

Each item's loan history is ordered by newest loan first and shows 10 records per page. Previous and Next retain the item barcode and reader search. Invalid page numbers fall back to page 1; requests beyond the last page show the last page.

Reader search also filters the selected item's loan history and its page count. Clear the search or select Show all readers' loan records to view the item's full history. A single matching checkout borrower is displayed directly; multiple matches require choosing the exact borrower.

## Reader self-service desk

All reader categories can open Desk from the navigation. Search by title keyword,
full title, author or exact barcode, then borrow an available physical copy.
The desk lists only the signed-in reader's active loans with Return buttons.
Borrower identity comes from the session; readers cannot return other readers' loans.
The librarian desk and overdue administration retain their existing behavior.

### Existing database upgrade

Apply `database/04_self_service.sql` once to each existing database, without resetting
or reseeding it. This makes `loan.librarian_id` nullable: NULL records a self-service
checkout; librarian-assisted loans still record the librarian ID. New installations
already have this definition in `database/01_schema.sql`.

The database configured for this development session was upgraded on 2026-11-27.
Other team databases need the same migration before using self-service checkout.

### Concurrency verification

Checkout locks the physical copy with `SELECT ... FOR UPDATE`, validates reader
eligibility under the reader lock, and commits loan creation and copy status together.
The existing unique open-loan constraint provides a second database safeguard.
Active-loan eligibility queries use locking reads so a concurrent checkout by the same
reader cannot validate limits against an older transaction snapshot.
Return checks ownership while holding the copy lock, then closes the loan, generates
fees and allocates any waiting reservation in the existing transaction.

Run the existing suite with `python -m unittest discover -v`.
For a real database contention test after applying the migration:

```powershell
$env:RUN_CIRCULATION_DB_TESTS = '1'
python -m unittest tests.test_circulation_concurrency -v
Remove-Item Env:RUN_CIRCULATION_DB_TESTS
```

This test creates two temporary readers and one title/copy, races their checkouts,
checks that exactly one succeeds, checks return ownership, and deletes its fixture
rows in cleanup. Run against a development database.
