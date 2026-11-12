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

- desk_context() returns the copy, readers and loans used by the desk template.
- borrow(reader_id, barcode) validates borrowing eligibility and commits the loan and copy changes together.
- return_copy(barcode) closes the loan and updates the copy in one transaction.

The shared routes in app/blueprints/desk.py call these functions. The desk page uses app/templates/desk/index.html and extends the shared base template.

## Demonstration

The desk retains the original demo scope, showing Clean Code, barcode KB-0001, and using the seed librarian with ID 1. Authentication will provide the acting librarian when the account module is integrated.

1. Choose alice and check out the item. Confirm its status becomes Borrowed and a loan with a 14-day period appears.
2. Refresh the page and confirm that the record remains.
3. Return the item. Confirm its status becomes Available and its return time appears.
4. Choose bob and attempt checkout. Confirm an overdue-loan message appears and no new loan is added.

Alice's original seed loan is due on 15 November 2026. After it becomes overdue, use carol before her seed loan becomes overdue on 19 December 2026, or first resolve Alice's overdue loan. Carol receives a 60-day borrowing period.

The services check copy availability, overdue loans, unpaid fees and distinct-title borrowing limits. Returns with a waiting reservation are refused until reservation allocation is integrated. Renewals, fee generation and reservation allocation remain future work.
