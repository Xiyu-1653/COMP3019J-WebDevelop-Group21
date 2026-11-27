-- Apply once to an existing database; preserves all loans and other data.
-- New installations already include this change in 01_schema.sql.
ALTER TABLE loan MODIFY COLUMN librarian_id INT UNSIGNED NULL;
