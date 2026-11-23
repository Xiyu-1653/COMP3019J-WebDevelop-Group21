# Implemented feature tests

Run from the repository root:

```powershell
python -m unittest discover -s tests -v
```

These tests use mocks and Flask test_client; no MySQL server or seed reset is needed. Route tests block real PyMySQL connections. The existing test_catalogue.py contains MySQL integration tests and requires a configured database.

Coverage: borrowing rules and distinct-title limits, returns and current waiting-reservation restriction, allocation, collection, expiration, authentication, permissions, My loans isolation, renewal ownership and once-only rules, and read-only fee history. Unimplemented reservation creation/cancellation, fee payments, notices and inventory editing are excluded.

Mock tests do not establish SQL correctness, real transaction rollback, database constraints, concurrency, or browser rendering. Those require separate MySQL integration/browser tests.
